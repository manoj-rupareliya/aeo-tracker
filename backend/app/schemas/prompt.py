"""
Prompt & Template Schemas
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


class PromptTemplateCreate(BaseModel):
    """Prompt template creation request"""
    name: str = Field(..., min_length=1, max_length=255)
    prompt_type: str = Field(..., pattern="^(informational|comparative|recommendation)$")
    template_text: str = Field(..., min_length=10)
    description: Optional[str] = None
    expected_output_format: Optional[str] = Field(None, pattern="^(paragraph|list|structured)$")


class PromptTemplateUpdate(BaseModel):
    """Prompt template update - creates new version"""
    template_text: str = Field(..., min_length=10)
    description: Optional[str] = None
    expected_output_format: Optional[str] = None
    version_bump: str = Field(default="patch", pattern="^(major|minor|patch)$")


class PromptTemplateResponse(BaseModel):
    """Prompt template response"""
    id: UUID
    name: str
    prompt_type: str
    template_text: str
    version: str  # e.g., "1.2.3"
    is_active: bool
    description: Optional[str]
    expected_output_format: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PromptResponse(BaseModel):
    """Generated prompt response"""
    id: UUID
    keyword_id: UUID
    template_id: Optional[UUID]
    prompt_type: str
    prompt_text: str
    prompt_hash: str
    injected_context: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class GeneratePromptsRequest(BaseModel):
    """Request to generate prompts for keywords"""
    keyword_ids: List[UUID] = Field(..., min_items=1, max_items=50)
    prompt_types: List[str] = Field(
        default=["informational", "comparative", "recommendation"],
        min_items=1
    )
    regenerate: bool = False  # If True, regenerate even if prompts exist


class GeneratePromptsResponse(BaseModel):
    """Response from prompt generation"""
    total_generated: int
    prompts_by_keyword: Dict[str, List[PromptResponse]]  # keyword_id -> prompts
    skipped_existing: int


class PromptPreview(BaseModel):
    """Preview a prompt before saving"""
    template_id: UUID
    keyword: str
    brand_name: str
    industry: str
    competitors: List[str] = []

    # Generated preview
    preview_text: Optional[str] = None
