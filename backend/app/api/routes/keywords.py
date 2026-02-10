"""
Keyword Management Routes
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Keyword, Project, Prompt, LLMRun, User
from app.schemas.keyword import (
    KeywordCreate, KeywordBulkCreate, KeywordUpdate,
    KeywordResponse, KeywordListResponse
)
from app.utils import get_db
from app.api.middleware.auth import get_current_user

router = APIRouter()


@router.post("/{project_id}", response_model=KeywordResponse, status_code=status.HTTP_201_CREATED)
async def create_keyword(
    project_id: UUID,
    keyword_data: KeywordCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a keyword to project"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    keyword = Keyword(
        project_id=project_id,
        keyword=keyword_data.keyword,
        context=keyword_data.context,
        priority=keyword_data.priority,
    )
    db.add(keyword)
    await db.commit()
    await db.refresh(keyword)

    return _keyword_to_response(keyword, db)


@router.post("/{project_id}/bulk", response_model=List[KeywordResponse], status_code=status.HTTP_201_CREATED)
async def create_keywords_bulk(
    project_id: UUID,
    bulk_data: KeywordBulkCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add multiple keywords to project"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Check for existing keywords
    result = await db.execute(
        select(Keyword.keyword).where(Keyword.project_id == project_id)
    )
    existing = set(row[0].lower() for row in result.fetchall())

    keywords = []
    for kw_text in bulk_data.keywords:
        if kw_text.lower() not in existing:
            keyword = Keyword(
                project_id=project_id,
                keyword=kw_text,
                priority=bulk_data.priority,
            )
            db.add(keyword)
            keywords.append(keyword)
            existing.add(kw_text.lower())

    await db.commit()

    return [await _keyword_to_response(k, db) for k in keywords]


@router.get("/{project_id}", response_model=KeywordListResponse)
async def list_keywords(
    project_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List keywords for a project"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Build query
    query = select(Keyword).where(Keyword.project_id == project_id)
    count_query = select(func.count(Keyword.id)).where(Keyword.project_id == project_id)

    if search:
        query = query.where(Keyword.keyword.ilike(f"%{search}%"))
        count_query = count_query.where(Keyword.keyword.ilike(f"%{search}%"))

    # Get total count
    result = await db.execute(count_query)
    total = result.scalar()

    # Get keywords
    result = await db.execute(
        query
        .order_by(Keyword.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    keywords = result.scalars().all()

    return KeywordListResponse(
        items=[await _keyword_to_response(k, db) for k in keywords],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{project_id}/{keyword_id}", response_model=KeywordResponse)
async def get_keyword(
    project_id: UUID,
    keyword_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get keyword details"""
    result = await db.execute(
        select(Keyword)
        .join(Project)
        .where(
            Keyword.id == keyword_id,
            Keyword.project_id == project_id,
            Project.owner_id == user.id
        )
    )
    keyword = result.scalar_one_or_none()

    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")

    return await _keyword_to_response(keyword, db)


@router.put("/{project_id}/{keyword_id}", response_model=KeywordResponse)
async def update_keyword(
    project_id: UUID,
    keyword_id: UUID,
    keyword_data: KeywordUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update keyword"""
    result = await db.execute(
        select(Keyword)
        .join(Project)
        .where(
            Keyword.id == keyword_id,
            Keyword.project_id == project_id,
            Project.owner_id == user.id
        )
    )
    keyword = result.scalar_one_or_none()

    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")

    if keyword_data.keyword is not None:
        keyword.keyword = keyword_data.keyword
    if keyword_data.context is not None:
        keyword.context = keyword_data.context
    if keyword_data.priority is not None:
        keyword.priority = keyword_data.priority
    if keyword_data.is_active is not None:
        keyword.is_active = keyword_data.is_active

    await db.commit()
    await db.refresh(keyword)

    return await _keyword_to_response(keyword, db)


@router.delete("/{project_id}/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword(
    project_id: UUID,
    keyword_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete keyword"""
    result = await db.execute(
        select(Keyword)
        .join(Project)
        .where(
            Keyword.id == keyword_id,
            Keyword.project_id == project_id,
            Project.owner_id == user.id
        )
    )
    keyword = result.scalar_one_or_none()

    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")

    await db.delete(keyword)
    await db.commit()


async def _keyword_to_response(keyword: Keyword, db: AsyncSession) -> KeywordResponse:
    """Convert Keyword model to response with stats"""
    # Get prompt count
    result = await db.execute(
        select(func.count(Prompt.id)).where(Prompt.keyword_id == keyword.id)
    )
    prompt_count = result.scalar()

    # Get run count
    result = await db.execute(
        select(func.count(LLMRun.id))
        .join(Prompt)
        .where(Prompt.keyword_id == keyword.id)
    )
    run_count = result.scalar()

    # Get average visibility score
    from app.models import VisibilityScore
    result = await db.execute(
        select(func.avg(VisibilityScore.total_score))
        .where(VisibilityScore.keyword_id == keyword.id)
    )
    avg_score = result.scalar()

    # Get last run
    result = await db.execute(
        select(LLMRun.completed_at)
        .join(Prompt)
        .where(Prompt.keyword_id == keyword.id)
        .order_by(LLMRun.completed_at.desc())
        .limit(1)
    )
    last_run = result.scalar_one_or_none()

    return KeywordResponse(
        id=keyword.id,
        keyword=keyword.keyword,
        context=keyword.context,
        priority=keyword.priority,
        is_active=keyword.is_active,
        created_at=keyword.created_at,
        updated_at=keyword.updated_at,
        prompt_count=prompt_count,
        run_count=run_count,
        avg_visibility_score=float(avg_score) if avg_score else None,
        last_run_at=last_run,
    )
