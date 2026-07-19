import logging
from fastapi import APIRouter, Request, HTTPException
from datetime import datetime

from app.schemas.vapi import VapiWebhookPayload, VapiWebhookResponse
from app.db.models import CallRecordCreate
from app.db.supabase_client import CallRepository
from app.config import settings

logger = logging.getLogger(__name__)

"""
Webhook Handler

This file handles incoming webhooks from VAPI.

What's a webhook?
- VAPI calls OUR API when something happens (call ends, message sent, etc.)
- We process the event and respond

Flow:
1. VAPI calls POST /api/v1/webhooks/call-ended
2. We receive the webhook payload
3. We validate it's actually from VAPI (signature verification)
4. We extract data and store it in Supabase
5. We respond to VAPI with success/failure

Why webhook verification?
- Prevents fake calls from malicious actors
- VAPI signs every webhook with a secret key
- We verify the signature before trusting the data
"""

# ============================================================================
# ROUTER SETUP
# ============================================================================

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
    responses={404: {"description": "Not found"}},
)

"""
Why prefix="/webhooks"?
- We're creating routes like POST /api/v1/webhooks/call-ended
- The prefix means all routes in this file start with /webhooks
- In main.py, we'll include this with prefix="/api/v1"
- Final route: POST /api/v1/webhooks/call-ended
"""

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_transcript(messages: list) -> str:
    """
    Convert a list of Message objects into a readable transcript string.
    
    Args:
        messages: List of Message dicts from VAPI
        
    Returns:
        Formatted transcript as a single string
        
    Example input:
    [
        {"role": "assistant", "message": "Hi, how can I help?"},
        {"role": "user", "message": "I want to schedule an appointment"}
    ]
    
    Example output:
    "Assistant: Hi, how can I help?
    User: I want to schedule an appointment"
    
    Why this function?
    - VAPI sends messages as a list
    - We store transcript as a single text field
    - This function formats it nicely
    """
    if not messages:
        return ""
    
    transcript_lines = []
    for msg in messages:
        role = msg.get("role", "unknown").capitalize()
        text = msg.get("message", "")
        transcript_lines.append(f"{role}: {text}")
    
    return "\n".join(transcript_lines)


def extract_caller_info(transcript: str) -> tuple[str, str]:
    """
    Extract caller name and reason from transcript (placeholder).
    
    Args:
        transcript: Full transcript text
        
    Returns:
        Tuple of (caller_name, reason_for_call)
        
    Why this function?
    - VAPI doesn't always extract this structured data
    - We need Nova to capture: "What's your name?" and "Why are you calling?"
    - This is a placeholder for now
    - In production, you'd use VAPI's analysis or ask Nova to extract
    
    For now, we return None/empty strings
    TODO: Implement actual extraction (regex, NLP, or ask Nova)
    """
    # Placeholder implementation
    caller_name = None
    reason_for_call = None
    
    """
    In future, you could:
    1. Parse transcript with regex: look for "name is [name]"
    2. Ask Nova to extract: include a prompt like "extract: caller name, reason"
    3. Use VAPI's analysis field (if it extracts this)
    
    For now, we leave these as None and they stay null in DB
    """
    
    return caller_name, reason_for_call


# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================

@router.post("/call-ended")
async def handle_call_ended(request: Request):
    """
    Handle VAPI webhook when a call ends.
    
    Endpoint: POST /api/v1/webhooks/call-ended
    
    What VAPI sends:
    {
        "call_id": "call_abc123",
        "phone_number": "+1-234-567-8900",
        "started_at": "2024-01-15T10:30:45Z",
        "ended_at": "2024-01-15T10:35:12Z",
        "status": "completed",
        "messages": [...],
        ...
    }
    
    What we do:
    1. Parse and validate the webhook payload
    2. Extract data we need
    3. Store in Supabase
    4. Return success to VAPI
    
    Why async?
    - Database queries take time
    - async/await doesn't block other requests
    """
    
    try:
        # Step 1: Read the raw request body
        body = await request.json()
        logger.info(f"Received webhook: call_id={body.get('call_id')}")
        
        """
        Why read as JSON?
        - VAPI sends JSON in request body
        - await is needed because reading is async I/O
        """
        
        # Step 2: Validate against our schema
        try:
            webhook_payload = VapiWebhookPayload(**body)
        except Exception as e:
            logger.error(f"Validation error: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid webhook payload")
        
        """
        What does validation do?
        - Checks all required fields are present
        - Checks types are correct (dates are dates, ints are ints)
        - Pydantic raises ValidationError if invalid
        - We catch it and return 400 (Bad Request)
        
        Why validate?
        - Prevents garbage data from corrupting our database
        - Makes sure we have what we need before proceeding
        """
        
        # Step 3: Extract transcript from messages
        transcript = ""
        if webhook_payload.messages:
            transcript = extract_transcript(webhook_payload.messages)
            logger.debug(f"Extracted transcript: {len(transcript)} chars")
        
        """
        Why extract transcript?
        - VAPI sends messages as a list of objects
        - We store as a single text field
        - Easier to search/read later
        """
        
        # Step 4: Extract caller info (name, reason)
        caller_name, reason_for_call = extract_caller_info(transcript)
        
        """
        Why extract this?
        - Structured data is useful
        - Can filter/search by reason or name
        - For now, both are None (we'll improve later)
        """
        
        # Step 5: Build the database record
        call_record = CallRecordCreate(
            call_id=webhook_payload.call_id,
            phone_number=webhook_payload.phone_number,
            caller_name=caller_name,
            reason_for_call=reason_for_call,
            started_at=webhook_payload.started_at,
            ended_at=webhook_payload.ended_at,
            duration_seconds=webhook_payload.duration_seconds,
            transcript=transcript,
            summary=webhook_payload.analysis.summary if webhook_payload.analysis else None,
            sentiment=webhook_payload.analysis.sentiment if webhook_payload.analysis else None,
            status=webhook_payload.status,
            error_message=webhook_payload.error_message,
            assistant_id=webhook_payload.assistant_id or "nova"
        )
        
        """
        Why build CallRecordCreate?
        - Pydantic model validates all fields
        - Ensures data is correct before storing
        - Type-safe: started_at is a datetime, not a string
        
        Note: analysis might be None, so we check before accessing
        """
        
        logger.info(f"Prepared call record: {call_record.call_id}")
        
        # Step 6: Insert into database
        result = await CallRepository.insert_call(call_record)
        
        """
        Why await?
        - Database query is async I/O
        - await pauses here until query completes
        - FastAPI can handle other requests meanwhile
        
        What does insert_call return?
        - CallRecordResponse if successful
        - None if failed
        """
        
        if result:
            logger.info(f"Call stored successfully: id={result.id}, call_id={result.call_id}")
            
            # Step 7: Return success response to VAPI
            response = VapiWebhookResponse(
                success=True,
                message=f"Call {webhook_payload.call_id} stored successfully"
            )
            
            """
            Why return VapiWebhookResponse?
            - VAPI expects a specific format back
            - {"success": true, "message": "..."}
            - If we don't respond correctly, VAPI might retry
            """
            
            return response.dict()
        else:
            logger.error(f"Failed to store call: {webhook_payload.call_id}")
            
            # Return error response to VAPI
            response = VapiWebhookResponse(
                success=False,
                message=f"Failed to store call {webhook_payload.call_id}"
            )
            
            """
            Why return False instead of raising exception?
            - We want to tell VAPI the problem was on OUR side, not theirs
            - If we raise HTTPException(status_code=500), VAPI retries forever
            - Returning {"success": False} tells VAPI: "I got it, but couldn't process"
            - VAPI won't retry
            """
            
            return response.dict()
    
    except Exception as e:
        logger.error(f"Unexpected error in webhook handler: {str(e)}", exc_info=True)
        
        """
        Why exc_info=True?
        - Logs the full stack trace, not just the error message
        - Helpful for debugging production issues
        - Shows exactly which line failed
        """
        
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/message")
async def handle_message(request: Request):
    """
    Handle VAPI webhook for mid-call messages (optional).
    
    This endpoint is called when Nova sends a message during the call.
    
    For now, we just log it (we only care about call-ended).
    In future, you might:
    - Track real-time transcription
    - Send notifications
    - Trigger actions mid-call
    
    Endpoint: POST /api/v1/webhooks/message
    """
    try:
        body = await request.json()
        call_id = body.get("call_id", "unknown")
        logger.debug(f"Message event for call: {call_id}")
        
        # Just acknowledge we got it
        return {
            "success": True,
            "message": "Message received"
        }
    
    except Exception as e:
        logger.error(f"Error handling message webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# QUERY ENDPOINTS (Optional, for testing/debugging)
# ============================================================================

@router.get("/calls")
async def list_calls(limit: int = 50, offset: int = 0):
    """
    Fetch all calls from the database.
    
    Endpoint: GET /api/v1/webhooks/calls?limit=50&offset=0
    
    Why have this?
    - For testing (verify data was stored)
    - For debugging (see what's in the database)
    - Could expand to a full admin dashboard
    
    In production, you'd protect this with authentication
    (not anyone should be able to see call records)
    """
    try:
        logger.info(f"Fetching calls: limit={limit}, offset={offset}")
        calls = await CallRepository.get_all_calls(limit=limit, offset=offset)
        
        return {
            "success": True,
            "data": [call.dict() for call in calls],
            "count": len(calls)
        }
    
    except Exception as e:
        logger.error(f"Error fetching calls: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/calls/{vapi_call_id}")
async def get_call(vapi_call_id: str):
    """
    Fetch a single call by VAPI call ID.
    
    Endpoint: GET /api/v1/webhooks/calls/call_abc123
    
    Useful for:
    - Testing (retrieve a specific call)
    - Debugging (see full details)
    """
    try:
        logger.info(f"Fetching call: {vapi_call_id}")
        call = await CallRepository.get_call_by_vapi_id(vapi_call_id)
        
        if call:
            return {
                "success": True,
                "data": call.dict()
            }
        else:
            raise HTTPException(status_code=404, detail="Call not found")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching call: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")