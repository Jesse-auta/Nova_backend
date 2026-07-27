import logging
import json
from fastapi import APIRouter, Request, HTTPException
from datetime import datetime, timezone

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
    return None, None


@router.post("/call-ended")
async def handle_call_ended(request: Request):
    try:
        body = await request.json()
        logger.info("===== FULL WEBHOOK PAYLOAD START =====")
        logger.info(json.dumps(body, indent=2, default=str))
        logger.info("===== FULL WEBHOOK PAYLOAD END =====")

        webhook_payload = VapiWebhookPayload(**body)

        call_id = webhook_payload.call_id
        if not call_id:
            call_id = body.get("call_id") or body.get("id") or f"call_{int(datetime.now(timezone.utc).timestamp())}"
            logger.warning(f"call_id was missing, using fallback: {call_id}")

        transcript = ""
        if webhook_payload.messages:
            transcript = extract_transcript([m.dict() for m in webhook_payload.messages])

        caller_name, reason_for_call = extract_caller_info(transcript)

        started_at = webhook_payload.started_at or datetime.now(timezone.utc)
        ended_at = webhook_payload.ended_at
        status = webhook_payload.status or "completed"

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

        result = await CallRepository.insert_call(call_record)

        if result:
            logger.info(f"✅ Call stored: id={result.id}, call_id={result.call_id}")
            return VapiWebhookResponse(success=True, message=f"Call {call_id} stored successfully").dict()
        else:
            logger.error(f"❌ Failed to store call: {call_id}")
            return VapiWebhookResponse(success=False, message=f"Failed to store call {call_id}").dict()

    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}", exc_info=True)
        return VapiWebhookResponse(success=False, message=f"Error: {str(e)}").dict()


@router.post("/message")
async def handle_message(request: Request):
    try:
        body = await request.json()
        call_id = body.get("call_id", "unknown")
        logger.debug(f"Message event for call: {call_id}")
        return {"success": True, "message": "Message received"}
    except Exception as e:
        logger.error(f"Error handling message webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/calls")
async def list_calls(limit: int = 50, offset: int = 0):
    try:
        calls = await CallRepository.get_all_calls(limit=limit, offset=offset)
        return {"success": True, "data": [c.dict() for c in calls], "count": len(calls)}
    except Exception as e:
        logger.error(f"Error fetching calls: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/calls/{vapi_call_id}")
async def get_call(vapi_call_id: str):
    try:
        call = await CallRepository.get_call_by_vapi_id(vapi_call_id)
        if call:
            return {"success": True, "data": call.dict()}
        raise HTTPException(status_code=404, detail="Call not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching call: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")