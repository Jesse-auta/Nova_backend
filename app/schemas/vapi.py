import logging
from fastapi import APIRouter, Request, HTTPException
from datetime import datetime
import json

from app.schemas.vapi import VapiWebhookPayload, VapiWebhookResponse
from app.db.models import CallRecordCreate
from app.db.supabase_client import CallRepository
from app.config import settings

logger = logging.getLogger(__name__)

"""
Webhook Handler for VAPI
"""

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
    responses={404: {"description": "Not found"}},
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_transcript(messages: list) -> str:
    """
    Convert list of messages into readable transcript string.
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
    """
    caller_name = None
    reason_for_call = None
    
    return caller_name, reason_for_call


# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================

@router.post("/call-ended")
async def handle_call_ended(request: Request):
    """
    Handle VAPI webhook when a call ends.
    """
    
    try:
        # Step 1: Read raw request
        body = await request.json()
        logger.info(f"Full webhook payload: {json.dumps(body, indent=2)}")
        
        # Step 2: Validate with flexible schema
        try:
            webhook_payload = VapiWebhookPayload(**body)
        except Exception as e:
            logger.error(f"Validation warning (non-fatal): {str(e)}")
            webhook_payload = VapiWebhookPayload()
        
        # Step 3: Extract call_id with fallback
        call_id = webhook_payload.call_id
        if not call_id:
            call_id = body.get("call_id") or body.get("id") or f"call_{int(datetime.utcnow().timestamp())}"
            logger.warning(f"call_id was None, using fallback: {call_id}")
        
        logger.info(f"Processing call: {call_id}")
        
        # Step 4: Extract transcript
        transcript = ""
        if webhook_payload.messages:
            transcript = extract_transcript(webhook_payload.messages)
        
        # Step 5: Extract caller info
        caller_name, reason_for_call = extract_caller_info(transcript)
        
        # Step 6: Extract timestamps with fallbacks
        started_at = webhook_payload.started_at
        if not started_at:
            started_at = datetime.utcnow()
            logger.warning("started_at was None, using current time")
        
        ended_at = webhook_payload.ended_at
        status = webhook_payload.status or "completed"
        
        # Step 7: Build database record
        call_record = CallRecordCreate(
            call_id=call_id,
            phone_number=webhook_payload.phone_number,
            caller_name=caller_name,
            reason_for_call=reason_for_call,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=webhook_payload.duration_seconds,
            transcript=transcript,
            summary=webhook_payload.analysis.summary if webhook_payload.analysis else None,
            sentiment=webhook_payload.analysis.sentiment if webhook_payload.analysis else None,
            status=status,
            error_message=webhook_payload.error_message,
            assistant_id=webhook_payload.assistant_id or "nova"
        )
        
        logger.info(f"Prepared call record: {call_record.call_id}")
        
        # Step 8: Insert into database
        result = await CallRepository.insert_call(call_record)
        
        if result:
            logger.info(f"Call stored successfully: id={result.id}, call_id={result.call_id}")
            return VapiWebhookResponse(
                success=True,
                message=f"Call {call_id} stored successfully"
            ).dict()
        else:
            logger.error(f"Failed to store call: {call_id}")
            return VapiWebhookResponse(
                success=False,
                message=f"Failed to store call {call_id}"
            ).dict()
    
    except Exception as e:
        logger.error(f"Unexpected error in webhook handler: {str(e)}", exc_info=True)
        return VapiWebhookResponse(
            success=False,
            message=f"Error: {str(e)}"
        ).dict()


@router.post("/message")
async def handle_message(request: Request):
    """
    Handle VAPI webhook for mid-call messages (optional).
    """
    try:
        body = await request.json()
        call_id = body.get("call_id", "unknown")
        logger.debug(f"Message event for call: {call_id}")
        
        return {
            "success": True,
            "message": "Message received"
        }
    
    except Exception as e:
        logger.error(f"Error handling message webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# QUERY ENDPOINTS
# ============================================================================

@router.get("/calls")
async def list_calls(limit: int = 50, offset: int = 0):
    """
    Fetch all calls from the database.
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