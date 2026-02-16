"""
Project Management Routes
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Project, Brand, Competitor, Keyword, LLMRun, User
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse,
    BrandCreate, BrandResponse, CompetitorCreate, CompetitorResponse
)
from app.utils import get_db
from app.api.middleware.auth import get_current_user

router = APIRouter()


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project"""
    # Create project
    project = Project(
        owner_id=user.id,
        name=project_data.name,
        description=project_data.description,
        domain=project_data.domain,
        industry=project_data.industry,
        country=project_data.country,
        enabled_llms=project_data.enabled_llms,
        crawl_frequency_days=project_data.crawl_frequency_days,
        next_crawl_at=datetime.utcnow() + timedelta(days=project_data.crawl_frequency_days),
    )
    db.add(project)
    await db.flush()

    # Add brands
    for brand_data in project_data.brands:
        brand = Brand(
            project_id=project.id,
            name=brand_data.name,
            is_primary=brand_data.is_primary,
            aliases=brand_data.aliases,
        )
        db.add(brand)

    # If no primary brand, create one from domain
    if not any(b.is_primary for b in project_data.brands):
        brand = Brand(
            project_id=project.id,
            name=project_data.domain.split(".")[0].capitalize(),
            is_primary=True,
            aliases=[],
        )
        db.add(brand)

    # Add competitors
    for comp_data in project_data.competitors:
        competitor = Competitor(
            project_id=project.id,
            name=comp_data.name,
            domain=comp_data.domain,
            aliases=comp_data.aliases,
        )
        db.add(competitor)

    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.brands), selectinload(Project.competitors))
        .where(Project.id == project.id)
    )
    project = result.scalar_one()

    return _project_to_response(project)


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's projects"""
    # Count total
    count_result = await db.execute(
        select(func.count(Project.id)).where(Project.owner_id == user.id)
    )
    total = count_result.scalar()

    # Get projects
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.brands), selectinload(Project.competitors))
        .where(Project.owner_id == user.id)
        .order_by(Project.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    projects = result.scalars().all()

    return ProjectListResponse(
        items=[_project_to_response(p) for p in projects],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get project details"""
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.brands), selectinload(Project.competitors))
        .where(Project.id == project_id, Project.owner_id == user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return _project_to_response(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update project"""
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.brands), selectinload(Project.competitors))
        .where(Project.id == project_id, Project.owner_id == user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Update fields
    if project_data.name is not None:
        project.name = project_data.name
    if project_data.description is not None:
        project.description = project_data.description
    if project_data.industry is not None:
        project.industry = project_data.industry
    if project_data.country is not None:
        project.country = project_data.country
    if project_data.enabled_llms is not None:
        project.enabled_llms = project_data.enabled_llms
    if project_data.crawl_frequency_days is not None:
        project.crawl_frequency_days = project_data.crawl_frequency_days
    if project_data.is_active is not None:
        project.is_active = project_data.is_active

    await db.commit()
    await db.refresh(project)

    return _project_to_response(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete project"""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await db.delete(project)
    await db.commit()


# Brand management
@router.post("/{project_id}/brands", response_model=BrandResponse)
async def add_brand(
    project_id: UUID,
    brand_data: BrandCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a brand to project"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    brand = Brand(
        project_id=project_id,
        name=brand_data.name,
        is_primary=brand_data.is_primary,
        aliases=brand_data.aliases,
    )
    db.add(brand)
    await db.commit()
    await db.refresh(brand)

    return brand


@router.delete("/{project_id}/brands/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brand(
    project_id: UUID,
    brand_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a brand"""
    result = await db.execute(
        select(Brand)
        .join(Project)
        .where(Brand.id == brand_id, Project.owner_id == user.id)
    )
    brand = result.scalar_one_or_none()

    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    await db.delete(brand)
    await db.commit()


# Competitor management
@router.post("/{project_id}/competitors", response_model=CompetitorResponse)
async def add_competitor(
    project_id: UUID,
    competitor_data: CompetitorCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a competitor to project"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    competitor = Competitor(
        project_id=project_id,
        name=competitor_data.name,
        domain=competitor_data.domain,
        aliases=competitor_data.aliases,
    )
    db.add(competitor)
    await db.commit()
    await db.refresh(competitor)

    return competitor


@router.delete("/{project_id}/competitors/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competitor(
    project_id: UUID,
    competitor_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a competitor"""
    result = await db.execute(
        select(Competitor)
        .join(Project)
        .where(Competitor.id == competitor_id, Project.owner_id == user.id)
    )
    competitor = result.scalar_one_or_none()

    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    await db.delete(competitor)
    await db.commit()


def _project_to_response(project: Project, keyword_count: int = 0, total_runs: int = 0) -> ProjectResponse:
    """Convert Project model to response schema"""
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        domain=project.domain,
        industry=project.industry,
        country=project.country or "in",
        enabled_llms=project.enabled_llms,
        crawl_frequency_days=project.crawl_frequency_days,
        last_crawl_at=project.last_crawl_at,
        next_crawl_at=project.next_crawl_at,
        is_active=project.is_active,
        created_at=project.created_at,
        updated_at=project.updated_at,
        brands=[BrandResponse.model_validate(b) for b in project.brands],
        competitors=[CompetitorResponse.model_validate(c) for c in project.competitors],
        keyword_count=keyword_count,
        total_runs=total_runs,
    )
