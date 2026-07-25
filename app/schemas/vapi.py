import logging
import json
from fastapi import APIRouter, Request, HTTPException
from datetime import datetime

from app.schemas.vapi import VapiWebhookPayload, VapiWebhookResponse
from app.db.models import CallRecordCreate
from app.db.supabase_client import CallRepository
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
    responses={404: {"description": "Not found"}},
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_transcript(messages: list) -> str:
    if not messages:
        return ""
    
    transcript_lines = []
    for msg in messages:
        role = msg.get("role", "unknown").capitalize()
        text = msg.get("message", "")
        transcript_lines.append(f"{role}: {text}")
    
    return "\n".join(transcript_lines)


def extract_caller_info(transcript: str) -> tuple[str, str]:
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
        # Step 1: Read raw request and log EVERYTHING
        body = await request.json()
        logger.info(f"===== FULL WEBHOOK PAYLOAD START =====")
        logger.info(json.dumps(body, indent=2, default=str))
        logger.info(f"===== FULL WEBHOOK PAYLOAD END =====")
        
        # Step 2: Validate
        webhook_payload = VapiWebhookPayload(**body)
        
        # Step 3: Extract with fallbacks
        call_id = webhook_payload.call_id
        if not call_id:
            call_id = body.get("call_id") or body.get("id") or f"call_{int(datetime.utcnow().timestamp())}"
            logger.warning(f"call_id was None/missing, using fallback: {call_id}")
        
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
        
        status = webhook_payload.status
        if not status:
            status = "completed"
            logger.warning("status was None, using 'completed'")
        
        # Step 7: Build record
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
        
        # Step 8: Insert
        result = await CallRepository.insert_call(call_record)
        
        if result:
            logger.info(f"✅ Call stored successfully: id={result.id}, call_id={result.call_id}")
            return VapiWebhookResponse(
                success=True,
                message=f"Call {call_id} stored successfully"
            ).dict()
        else:
            logger.error(f"❌ Failed to store call: {call_id}")
            return VapiWebhookResponse(
                success=False,
                message=f"Failed to store call {call_id}"
            ).dict()
    
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}", exc_info=True)
        return VapiWebhookResponse(
            success=False,
            message=f"Error: {str(e)}"
        ).dict()


@router.post("/message")
async def handle_message(request: Request):
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


@router.get("/calls")
async def list_calls(limit: int = 50, offset: int = 0):
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