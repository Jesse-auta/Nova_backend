import logging
from supabase import create_client, Client
from typing import Optional, List
from datetime import datetime

from app.config import settings
from app.db.models import CallRecord, CallRecordCreate, CallRecordResponse

logger = logging.getLogger(__name__)

"""
Supabase Client

This is a singleton instance that manages all database operations.
We create it once and reuse it everywhere.

Why Supabase?
- PostgreSQL under the hood (powerful, reliable)
- HTTP API (easier than raw SQL)
- Real-time capabilities (we don't use yet, but available)
- Easy to deploy alongside FastAPI
"""

# ============================================================================
# SUPABASE CLIENT INITIALIZATION
# ============================================================================

supabase: Client = create_client(
    supabase_url=settings.SUPABASE_URL,
    supabase_key=settings.SUPABASE_KEY
)

"""
Why create_client()?
- Initializes connection to Supabase
- Uses URL and key from .env (loaded by settings)
- Returns a Client object we use for all queries
- This runs once when the app starts

Example:
settings.SUPABASE_URL = "https://myproject.supabase.co"
settings.SUPABASE_KEY = "eyJxx..."
-> Client connects to that Supabase project
"""

logger.info(f"Supabase client initialized: {settings.SUPABASE_URL}")


# ============================================================================
# CALL RECORD OPERATIONS
# ============================================================================

class CallRepository:
    """
    Repository pattern for call records.
    
    What's a repository?
    - Centralized place for all database queries
    - Keeps data access logic separate from business logic
    - Makes testing easier (can mock this)
    - If Supabase changes, we only update here
    
    All methods are async (non-blocking I/O):
    - await insert_call() waits for database
    - Meanwhile, FastAPI can handle other requests
    - No blocking, no thread pool needed
    """

    TABLE_NAME = "calls"
    """
    This is the table name in Supabase.
    
    Why store as constant?
    - If table name changes, update in one place
    - Prevents typos in queries
    - Clearer code
    """

    @staticmethod
    async def insert_call(call_data: CallRecordCreate) -> Optional[CallRecordResponse]:
        """
        Insert a new call record into the database.
        
        Args:
            call_data: CallRecordCreate object with call info
            
        Returns:
            The inserted CallRecordResponse (with id and created_at), or None if failed
            
        Why async?
        - Database query takes time (network latency)
        - async/await lets us do other work while waiting
        - FastAPI handles multiple requests concurrently
        
        Workflow:
        1. Convert Pydantic model to dict
        2. Insert into Supabase
        3. Return the inserted record
        4. If error, log it and return None
        """
        try:
            logger.info(f"Inserting call record: {call_data.call_id}")
            
            # Convert Pydantic model to dict (Supabase expects dict)
            data = call_data.dict()
            
            # Insert into Supabase (returns the inserted row)
            response = supabase.table(CallRepository.TABLE_NAME).insert(data).execute()
            
            """
            What's response.data?
            - If successful, it's a list with the inserted row
            - Example: [{"id": 1, "call_id": "call_123", ...}]
            - If empty list, something went wrong
            """
            
            if response.data and len(response.data) > 0:
                inserted_record = response.data[0]
                logger.info(f"Call inserted successfully: id={inserted_record.get('id')}, call_id={inserted_record.get('call_id')}")
                
                # Convert to response model (validates structure)
                return CallRecordResponse(**inserted_record)
            else:
                logger.error(f"Insert returned no data for call_id: {call_data.call_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error inserting call: {str(e)}")
            return None

    @staticmethod
    async def get_call_by_id(call_id_db: int) -> Optional[CallRecordResponse]:
        """
        Fetch a single call record by database ID.
        
        Args:
            call_id_db: The database ID (not VAPI call_id)
            
        Returns:
            CallRecordResponse if found, None otherwise
            
        Difference:
        - call_id_db = OUR database ID (1, 2, 3, ...)
        - call_id = VAPI's call ID ("call_abc123")
        
        Why have both?
        - Database ID is fast lookup
        - VAPI ID is external identifier
        """
        try:
            logger.info(f"Fetching call by database id: {call_id_db}")
            
            # Query: SELECT * FROM calls WHERE id = ?
            response = supabase.table(CallRepository.TABLE_NAME).select("*").eq("id", call_id_db).execute()
            
            if response.data and len(response.data) > 0:
                return CallRecordResponse(**response.data[0])
            else:
                logger.warning(f"Call not found: id={call_id_db}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching call: {str(e)}")
            return None

    @staticmethod
    async def get_call_by_vapi_id(vapi_call_id: str) -> Optional[CallRecordResponse]:
        """
        Fetch a call by VAPI's call ID.
        
        Args:
            vapi_call_id: VAPI's unique call ID (e.g., "call_abc123")
            
        Returns:
            CallRecordResponse if found, None otherwise
            
        Why this method?
        - VAPI sends us their call_id in webhooks
        - We need to find the corresponding record in our DB
        - Useful for updates: webhook arrives -> find record -> update it
        """
        try:
            logger.info(f"Fetching call by VAPI call_id: {vapi_call_id}")
            
            # Query: SELECT * FROM calls WHERE call_id = ?
            response = supabase.table(CallRepository.TABLE_NAME).select("*").eq("call_id", vapi_call_id).execute()
            
            if response.data and len(response.data) > 0:
                return CallRecordResponse(**response.data[0])
            else:
                logger.info(f"Call not found: call_id={vapi_call_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching call by VAPI ID: {str(e)}")
            return None

    @staticmethod
    async def get_all_calls(limit: int = 100, offset: int = 0) -> List[CallRecordResponse]:
        """
        Fetch multiple call records (with pagination).
        
        Args:
            limit: How many records to return (default 100, max probably lower)
            offset: How many to skip (for pagination)
            
        Returns:
            List of CallRecordResponse objects
            
        Why pagination?
        - Don't fetch millions of records at once (slow, memory-intensive)
        - Limit = "return 100 records"
        - Offset = "skip the first 50, then return 100"
        - Allows API: GET /calls?limit=50&offset=100
        
        Example:
        - First page: limit=50, offset=0 -> records 0-49
        - Second page: limit=50, offset=50 -> records 50-99
        - Third page: limit=50, offset=100 -> records 100-149
        """
        try:
            logger.info(f"Fetching all calls: limit={limit}, offset={offset}")
            
            # Query with order (newest first), limit, offset
            response = (
                supabase.table(CallRepository.TABLE_NAME)
                .select("*")
                .order("created_at", desc=True)  # Newest first
                .range(offset, offset + limit - 1)  # Pagination
                .execute()
            )
            
            if response.data:
                return [CallRecordResponse(**record) for record in response.data]
            else:
                logger.info("No calls found")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching all calls: {str(e)}")
            return []

    @staticmethod
    async def update_call(vapi_call_id: str, update_data: dict) -> Optional[CallRecordResponse]:
        """
        Update an existing call record.
        
        Args:
            vapi_call_id: VAPI's call ID (to find which record to update)
            update_data: Dict of fields to update
            
        Returns:
            Updated CallRecordResponse, or None if failed
            
        Example usage:
        - Webhook comes in with call_id = "call_abc123"
        - We find the record by call_id
        - We update status = "completed", transcript = "..."
        - We get back the updated record
        
        Why dict instead of model?
        - Flexibility: update just status, or status + transcript, or any combo
        - Model would require all fields
        """
        try:
            logger.info(f"Updating call: {vapi_call_id}, updates: {update_data.keys()}")
            
            # Update: set fields where call_id = ?
            response = (
                supabase.table(CallRepository.TABLE_NAME)
                .update(update_data)
                .eq("call_id", vapi_call_id)
                .execute()
            )
            
            if response.data and len(response.data) > 0:
                logger.info(f"Call updated successfully: {vapi_call_id}")
                return CallRecordResponse(**response.data[0])
            else:
                logger.error(f"Update returned no data: {vapi_call_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error updating call: {str(e)}")
            return None

    @staticmethod
    async def delete_call(vapi_call_id: str) -> bool:
        """
        Delete a call record (rarely used, kept for completeness).
        
        Args:
            vapi_call_id: VAPI call ID to delete
            
        Returns:
            True if successful, False otherwise
            
        Why keep this?
        - GDPR compliance (users might request deletion)
        - Testing (clean up test data)
        - Usually avoid in production (audit trail)
        """
        try:
            logger.warning(f"Deleting call: {vapi_call_id}")
            
            response = (
                supabase.table(CallRepository.TABLE_NAME)
                .delete()
                .eq("call_id", vapi_call_id)
                .execute()
            )
            
            logger.info(f"Call deleted: {vapi_call_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting call: {str(e)}")
            return False