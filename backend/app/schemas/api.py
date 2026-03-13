from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SkillSummaryResponse(BaseModel):
    id: str
    name: str
    version: str
    description: str
    engine: str
    renderers: Dict[str, Any]


class SkillDetailResponse(SkillSummaryResponse):
    manifest: Dict[str, Any]
    prompt_text: str


class ConversationCreateRequest(BaseModel):
    title: Optional[str] = None
    skillId: str = Field(..., min_length=1)


class ConversationResponse(BaseModel):
    id: str
    title: str
    skillId: str
    skillVersion: str
    status: str
    activeRunId: Optional[str]
    updatedAt: str


class MessageCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)


class MessageResponse(BaseModel):
    id: str
    conversationId: str
    runId: Optional[str]
    role: str
    uiParts: List[Dict[str, Any]]
    status: str
    createdAt: str


class MessageCreateResponse(BaseModel):
    conversationId: str
    userMessageId: str
    assistantMessageId: str
    runId: str
    status: str


class RunCancelResponse(BaseModel):
    runId: str
    status: str
