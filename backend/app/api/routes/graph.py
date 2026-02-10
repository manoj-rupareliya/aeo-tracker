"""
LLM Preference Graph API Routes
Query and visualize LLM-source-brand relationships
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, User
from app.models.database import LLMProvider
from app.models.models_v2 import (
    PreferenceGraphNode, PreferenceGraphEdge, SourceAuthority,
    LLMBehaviorProfile, GraphNodeType, GraphEdgeType
)
from app.services.graph_service import PreferenceGraphEngine
from app.utils import get_db
from app.api.middleware.auth import get_current_user

router = APIRouter()


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class GraphNodeResponse(BaseModel):
    """Response model for graph nodes."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    node_type: str
    node_identifier: str
    display_name: Optional[str]
    authority_score: Optional[float]
    persistence_score: Optional[float]
    citation_count: Optional[int]
    mention_count: Optional[int]
    created_at: datetime
    updated_at: datetime


class GraphEdgeResponse(BaseModel):
    """Response model for graph edges."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_node_id: UUID
    target_node_id: UUID
    edge_type: str
    weight: float
    frequency: int
    recency_score: float
    first_observed: datetime
    last_observed: datetime
    observation_count: int


class SourceAuthorityResponse(BaseModel):
    """Response model for source authority."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    provider: str
    citation_count: int
    citation_frequency: float
    position_avg: Optional[float]
    recency_weighted_score: float
    citation_trend: Optional[str]
    updated_at: datetime


class LLMBehaviorProfileResponse(BaseModel):
    """Response model for LLM behavior profiles."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    avg_citations_per_response: Optional[float]
    citation_source_diversity: Optional[float]
    avg_brands_mentioned: Optional[float]
    avg_response_length: Optional[int]
    response_consistency_score: Optional[float]
    total_runs_analyzed: int
    analysis_period_days: Optional[int]
    updated_at: datetime


# ============================================================================
# GRAPH NODE ENDPOINTS
# ============================================================================

@router.get("/nodes/{project_id}")
async def get_graph_nodes(
    project_id: UUID,
    node_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get nodes in the preference graph.
    Optionally filter by node type.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    from sqlalchemy import or_

    query = select(PreferenceGraphNode).where(
        or_(
            PreferenceGraphNode.project_id == project_id,
            PreferenceGraphNode.project_id.is_(None),  # Include global nodes (LLMs)
        )
    )

    if node_type:
        try:
            nt = GraphNodeType(node_type)
            query = query.where(PreferenceGraphNode.node_type == nt)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid node type: {node_type}")

    query = query.order_by(PreferenceGraphNode.authority_score.desc().nullslast()).limit(limit)

    result = await db.execute(query)
    nodes = list(result.scalars().all())

    return {
        "project_id": str(project_id),
        "total_nodes": len(nodes),
        "nodes": [GraphNodeResponse.model_validate(n) for n in nodes],
    }


@router.get("/edges/{project_id}")
async def get_graph_edges(
    project_id: UUID,
    edge_type: Optional[str] = Query(None),
    source_node_id: Optional[UUID] = Query(None),
    target_node_id: Optional[UUID] = Query(None),
    min_weight: Optional[float] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get edges in the preference graph.
    Filter by type, nodes, or minimum weight.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    query = select(PreferenceGraphEdge).where(PreferenceGraphEdge.project_id == project_id)

    if edge_type:
        try:
            et = GraphEdgeType(edge_type)
            query = query.where(PreferenceGraphEdge.edge_type == et)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid edge type: {edge_type}")

    if source_node_id:
        query = query.where(PreferenceGraphEdge.source_node_id == source_node_id)

    if target_node_id:
        query = query.where(PreferenceGraphEdge.target_node_id == target_node_id)

    if min_weight:
        query = query.where(PreferenceGraphEdge.weight >= min_weight)

    query = query.order_by(PreferenceGraphEdge.weight.desc()).limit(limit)

    result = await db.execute(query)
    edges = list(result.scalars().all())

    return {
        "project_id": str(project_id),
        "total_edges": len(edges),
        "edges": [GraphEdgeResponse.model_validate(e) for e in edges],
    }


# ============================================================================
# LLM PREFERENCE ENDPOINTS
# ============================================================================

@router.get("/llm/{project_id}/{provider}/preferred-sources")
async def get_llm_preferred_sources(
    project_id: UUID,
    provider: str,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get the sources most preferred/cited by a specific LLM.
    Ranked by citation weight and recency.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        llm_provider = LLMProvider(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

    graph_engine = PreferenceGraphEngine(db)
    sources = await graph_engine.get_llm_preferred_sources(
        llm_provider, project_id, limit
    )

    return {
        "provider": provider,
        "project_id": str(project_id),
        "preferred_sources": sources,
    }


@router.get("/llm/{project_id}/profiles")
async def get_llm_behavior_profiles(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get behavior profiles for all LLMs.
    Shows how each LLM behaves in terms of citations, mentions, etc.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(select(LLMBehaviorProfile))
    profiles = list(result.scalars().all())

    return {
        "project_id": str(project_id),
        "profiles": [LLMBehaviorProfileResponse.model_validate(p) for p in profiles],
    }


@router.post("/llm/{project_id}/{provider}/update-profile")
async def update_llm_profile(
    project_id: UUID,
    provider: str,
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Recalculate and update the behavior profile for an LLM.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        llm_provider = LLMProvider(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

    graph_engine = PreferenceGraphEngine(db)
    profile = await graph_engine.update_llm_behavior_profile(
        llm_provider, project_id, days
    )

    await db.commit()

    if not profile:
        raise HTTPException(status_code=404, detail="No data available for profile")

    return LLMBehaviorProfileResponse.model_validate(profile)


# ============================================================================
# BRAND AFFINITY ENDPOINTS
# ============================================================================

@router.get("/brand/{project_id}/{brand_name}/affinity")
async def get_brand_llm_affinity(
    project_id: UUID,
    brand_name: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get how well a brand is represented across different LLMs.
    Shows which LLMs mention the brand most frequently.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    graph_engine = PreferenceGraphEngine(db)
    affinity = await graph_engine.get_brand_llm_affinity(brand_name, project_id)

    return {
        "project_id": str(project_id),
        **affinity,
    }


@router.get("/brand/{project_id}/{brand_name}/sources")
async def get_brand_associated_sources(
    project_id: UUID,
    brand_name: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get sources that are frequently associated with a brand.
    These are sources that appear when the brand is mentioned.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Find sources associated with this brand by looking at ASSOCIATED edges
    from sqlalchemy import and_

    graph_engine = PreferenceGraphEngine(db)
    brand_node = await graph_engine.get_node(
        GraphNodeType.BRAND,
        brand_name.lower(),
        project_id,
    )

    if not brand_node:
        return {
            "brand": brand_name,
            "associated_sources": [],
        }

    # Get edges where brand is target of ASSOCIATED relationship
    result = await db.execute(
        select(PreferenceGraphEdge, PreferenceGraphNode)
        .join(PreferenceGraphNode, PreferenceGraphEdge.source_node_id == PreferenceGraphNode.id)
        .where(
            and_(
                PreferenceGraphEdge.target_node_id == brand_node.id,
                PreferenceGraphEdge.edge_type == GraphEdgeType.ASSOCIATED,
            )
        )
        .order_by(PreferenceGraphEdge.weight.desc())
    )

    sources = []
    for edge, source_node in result.all():
        sources.append({
            "domain": source_node.node_identifier,
            "association_strength": edge.weight,
            "co_occurrence_count": edge.frequency,
        })

    return {
        "brand": brand_name,
        "associated_sources": sources,
    }


# ============================================================================
# SOURCE AUTHORITY ENDPOINTS
# ============================================================================

@router.get("/sources/{project_id}/authority")
async def get_source_authority_rankings(
    project_id: UUID,
    provider: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get authority rankings for sources.
    Optionally filter by LLM provider.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    from app.models import CitationSource

    query = select(SourceAuthority, CitationSource).join(
        CitationSource, SourceAuthority.source_id == CitationSource.id
    )

    if provider:
        try:
            llm_provider = LLMProvider(provider)
            query = query.where(SourceAuthority.provider == llm_provider)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

    query = query.order_by(SourceAuthority.recency_weighted_score.desc()).limit(limit)

    result = await db.execute(query)
    authorities = result.all()

    return {
        "project_id": str(project_id),
        "provider_filter": provider,
        "sources": [
            {
                "domain": src.domain,
                "site_name": src.site_name,
                "category": src.category.value if src.category else None,
                "authority": SourceAuthorityResponse.model_validate(auth),
            }
            for auth, src in authorities
        ],
    }


@router.get("/sources/{project_id}/{domain}/associations")
async def get_source_brand_associations(
    project_id: UUID,
    domain: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get brands associated with a specific source.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    graph_engine = PreferenceGraphEngine(db)
    associations = await graph_engine.get_source_brand_associations(domain, project_id)

    return {
        "domain": domain,
        "project_id": str(project_id),
        "associated_brands": associations,
    }


# ============================================================================
# AUTHORITY HUB ENDPOINTS
# ============================================================================

@router.get("/hubs/{project_id}")
async def find_authority_hubs(
    project_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Find authority hubs - domains heavily cited across multiple LLMs.
    These are high-value targets for GEO.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    graph_engine = PreferenceGraphEngine(db)
    hubs = await graph_engine.find_authority_hubs(project_id, limit)

    return {
        "project_id": str(project_id),
        "authority_hubs": hubs,
    }


# ============================================================================
# GRAPH STATISTICS ENDPOINTS
# ============================================================================

@router.get("/stats/{project_id}")
async def get_graph_stats(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get statistics about the preference graph.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    graph_engine = PreferenceGraphEngine(db)
    stats = await graph_engine.get_graph_stats(project_id)

    return stats


@router.get("/visualization/{project_id}")
async def get_graph_visualization_data(
    project_id: UUID,
    max_nodes: int = Query(100, ge=10, le=500),
    min_edge_weight: float = Query(1.0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get graph data formatted for visualization (e.g., D3.js, vis.js).
    Returns nodes and edges in a format suitable for graph rendering.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    from sqlalchemy import or_

    # Get nodes
    result = await db.execute(
        select(PreferenceGraphNode)
        .where(
            or_(
                PreferenceGraphNode.project_id == project_id,
                PreferenceGraphNode.project_id.is_(None),
            )
        )
        .order_by(PreferenceGraphNode.authority_score.desc().nullslast())
        .limit(max_nodes)
    )
    nodes = list(result.scalars().all())
    node_ids = {n.id for n in nodes}

    # Get edges between these nodes
    result = await db.execute(
        select(PreferenceGraphEdge)
        .where(
            PreferenceGraphEdge.project_id == project_id,
            PreferenceGraphEdge.weight >= min_edge_weight,
            PreferenceGraphEdge.source_node_id.in_(node_ids),
            PreferenceGraphEdge.target_node_id.in_(node_ids),
        )
    )
    edges = list(result.scalars().all())

    # Format for visualization
    vis_nodes = [
        {
            "id": str(n.id),
            "label": n.display_name or n.node_identifier,
            "type": n.node_type.value,
            "size": n.citation_count or n.mention_count or 1,
            "authority": n.authority_score or 0,
        }
        for n in nodes
    ]

    vis_edges = [
        {
            "source": str(e.source_node_id),
            "target": str(e.target_node_id),
            "type": e.edge_type.value,
            "weight": e.weight,
        }
        for e in edges
    ]

    return {
        "nodes": vis_nodes,
        "edges": vis_edges,
        "node_count": len(vis_nodes),
        "edge_count": len(vis_edges),
    }
