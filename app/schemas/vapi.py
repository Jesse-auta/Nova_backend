from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

"""
VAPI Webhook Schemas
"""

# ============================================================================
# MESSAGE MODELS
# ============================================================================

class Message(BaseModel):
    role: Optional[str] = Field(None, description="'user' or 'assistant'")
    message: Optional[str] = Field(None, description="The actual text")
    timestamp: Optional[int] = Field(None, description="Unix timestamp")

    class Config:
        populate_by_name = True
        extra = "allow"


# ============================================================================
# ANALYSIS MODEL
# ============================================================================

class AnalysisResult(BaseModel):
    summary: Optional[str] = Field(None, description="Summary of the call")
    sentiment: Optional[str] = Field(None, description="Sentiment: positive, negative, neutral")
    action_items: Optional[List[str]] = Field(None, description="Action items from call")
    custom_analysis: Optional[dict] = Field(None, description="Custom analysis")

    class Config:
        populate_by_name = True
        extra = "allow"


# ============================================================================
# MAIN WEBHOOK PAYLOAD
# ============================================================================

class VapiWebhookPayload(BaseModel):
    """
    VAPI webhook payload - flexible to handle various event types
    """
    
    call_id: Optional[str] = Field(None, description="Unique call ID from VAPI")
    phone_number: Optional[str] = Field(None, description="Caller's phone number")
    assistant_id: Optional[str] = Field(None, description="Assistant ID")
    
    started_at: Optional[datetime] = Field(None, description="When call started")
    ended_at: Optional[datetime] = Field(None, description="When call ended")
    duration_seconds: Optional[int] = Field(None, description="Call duration")
    
    messages: Optional[List[Message]] = Field(None, description="Call transcript")
    analysis: Optional[AnalysisResult] = Field(None, description="Post-call analysis")
    
    status: Optional[str] = Field(None, description="Call status: completed, failed, ended")
    error_message: Optional[str] = Field(None, description="Error if status is failed")
    
    model: Optional[str] = Field(None, description="LLM model used")
    webhook_event_type: Optional[str] = Field(None, description="Type of webhook event")

    class Config:
        populate_by_name = True
        extra = "allow"


# ============================================================================
# WEBHOOK RESPONSE
# ============================================================================

class VapiWebhookResponse(BaseModel):
    success: bool = Field(..., description="Whether we processed the webhook")
    message: str = Field(..., description="Status message")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Call data stored successfully"
            }
        }