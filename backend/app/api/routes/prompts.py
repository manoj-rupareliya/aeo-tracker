"""
Prompt Management Routes
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, Keyword, Prompt, PromptTemplate, User, PromptType
from app.schemas.prompt import (
    PromptTemplateCreate, PromptTemplateResponse, PromptResponse,
    GeneratePromptsRequest, GeneratePromptsResponse
)
from app.services.prompt_engine import PromptEngine
from app.utils import get_db
from app.api.middleware.auth import get_current_user

router = APIRouter()


@router.get("/templates", response_model=List[PromptTemplateResponse])
async def list_templates(
    prompt_type: str = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List active prompt templates"""
    query = select(PromptTemplate).where(PromptTemplate.is_active == True)

    if prompt_type:
        query = query.where(PromptTemplate.prompt_type == prompt_type)

    result = await db.execute(query.order_by(PromptTemplate.name))
    templates = result.scalars().all()

    return [_template_to_response(t) for t in templates]


@router.post("/templates", response_model=PromptTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: PromptTemplateCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new prompt template"""
    template = PromptTemplate(
        name=template_data.name,
        prompt_type=PromptType(template_data.prompt_type),
        template_text=template_data.template_text,
        description=template_data.description,
        expected_output_format=template_data.expected_output_format,
        version_major=1,
        version_minor=0,
        version_patch=0,
        is_active=True,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    return _template_to_response(template)


@router.post("/templates/sync")
async def sync_templates(
    version: str = Query("v1"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Sync templates from YAML files to database"""
    engine = PromptEngine(db)
    synced = await engine.sync_templates_to_db(version)
    return {"synced": synced, "version": version}


@router.post("/{project_id}/generate", response_model=GeneratePromptsResponse)
async def generate_prompts(
    project_id: UUID,
    request: GeneratePromptsRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate prompts for keywords"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Convert prompt types
    prompt_types = None
    if request.prompt_types:
        prompt_types = [PromptType(pt) for pt in request.prompt_types]

    engine = PromptEngine(db)
    results = await engine.generate_prompts_for_project(
        project_id=str(project_id),
        keyword_ids=[str(kid) for kid in request.keyword_ids],
        prompt_types=prompt_types,
        regenerate=request.regenerate,
    )

    # Count results
    total_generated = sum(len(prompts) for prompts in results.values())

    # Convert to response format
    prompts_by_keyword = {}
    for keyword_id, prompts in results.items():
        prompts_by_keyword[keyword_id] = [
            PromptResponse(
                id=p.id,
                keyword_id=p.keyword_id,
                template_id=p.template_id,
                prompt_type=p.prompt_type.value,
                prompt_text=p.prompt_text,
                prompt_hash=p.prompt_hash,
                injected_context=p.injected_context,
                created_at=p.created_at,
            )
            for p in prompts
        ]

    return GeneratePromptsResponse(
        total_generated=total_generated,
        prompts_by_keyword=prompts_by_keyword,
        skipped_existing=0,  # Calculate if needed
    )


@router.get("/{project_id}/keyword/{keyword_id}", response_model=List[PromptResponse])
async def get_keyword_prompts(
    project_id: UUID,
    keyword_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get prompts for a keyword"""
    # Verify access
    result = await db.execute(
        select(Keyword)
        .join(Project)
        .where(
            Keyword.id == keyword_id,
            Keyword.project_id == project_id,
            Project.owner_id == user.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Keyword not found")

    result = await db.execute(
        select(Prompt).where(Prompt.keyword_id == keyword_id)
    )
    prompts = result.scalars().all()

    return [
        PromptResponse(
            id=p.id,
            keyword_id=p.keyword_id,
            template_id=p.template_id,
            prompt_type=p.prompt_type.value,
            prompt_text=p.prompt_text,
            prompt_hash=p.prompt_hash,
            injected_context=p.injected_context,
            created_at=p.created_at,
        )
        for p in prompts
    ]


def _template_to_response(template: PromptTemplate) -> PromptTemplateResponse:
    """Convert template to response"""
    return PromptTemplateResponse(
        id=template.id,
        name=template.name,
        prompt_type=template.prompt_type.value,
        template_text=template.template_text,
        version=template.version,
        is_active=template.is_active,
        description=template.description,
        expected_output_format=template.expected_output_format,
        created_at=template.created_at,
    )
