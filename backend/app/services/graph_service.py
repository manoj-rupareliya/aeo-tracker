"""
LLM Preference Graph Engine
Builds and maintains a graph of relationships between LLMs, sources, and brands
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
import math

from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import LLMProvider, Citation, CitationSource, BrandMention, LLMRun, LLMResponse
from ..models.models_v2 import (
    PreferenceGraphNode, PreferenceGraphEdge, SourceAuthority, LLMBehaviorProfile,
    GraphNodeType, GraphEdgeType
)


class PreferenceGraphEngine:
    """
    Engine for building and querying the LLM Preference Graph.

    Node Types:
    - LLM: The AI providers (ChatGPT, Claude, Gemini, Perplexity)
    - Domain: Source websites that are cited
    - Brand: Tracked entities (your brand and competitors)
    - Keyword: Search/prompt keywords

    Edge Types:
    - CITES: LLM → Domain (how often an LLM cites a source)
    - MENTIONS: LLM → Brand (how often an LLM mentions a brand)
    - ASSOCIATED: Domain → Brand (which brands are associated with which sources)
    - RELATED: Keyword → Keyword (semantic relationships)
    """

    # Decay factor for recency scoring (per day)
    RECENCY_DECAY = 0.98

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # NODE MANAGEMENT
    # =========================================================================

    async def get_or_create_node(
        self,
        node_type: GraphNodeType,
        node_identifier: str,
        project_id: Optional[UUID] = None,
        display_name: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> PreferenceGraphNode:
        """Get or create a node in the preference graph."""
        # Check if node exists
        query = select(PreferenceGraphNode).where(
            and_(
                PreferenceGraphNode.node_type == node_type,
                PreferenceGraphNode.node_identifier == node_identifier,
            )
        )

        if project_id:
            query = query.where(PreferenceGraphNode.project_id == project_id)
        else:
            query = query.where(PreferenceGraphNode.project_id.is_(None))

        result = await self.db.execute(query)
        node = result.scalar_one_or_none()

        if node:
            return node

        # Create new node
        node = PreferenceGraphNode(
            node_type=node_type,
            node_identifier=node_identifier,
            display_name=display_name or node_identifier,
            properties=properties or {},
            project_id=project_id,
        )
        self.db.add(node)
        await self.db.flush()
        return node

    async def get_node(
        self,
        node_type: GraphNodeType,
        node_identifier: str,
        project_id: Optional[UUID] = None,
    ) -> Optional[PreferenceGraphNode]:
        """Get a node by type and identifier."""
        query = select(PreferenceGraphNode).where(
            and_(
                PreferenceGraphNode.node_type == node_type,
                PreferenceGraphNode.node_identifier == node_identifier,
            )
        )

        if project_id:
            query = query.where(PreferenceGraphNode.project_id == project_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_node_metrics(
        self,
        node_id: UUID,
        authority_score: Optional[float] = None,
        persistence_score: Optional[float] = None,
        citation_count: Optional[int] = None,
        mention_count: Optional[int] = None,
    ) -> None:
        """Update computed metrics on a node."""
        result = await self.db.execute(
            select(PreferenceGraphNode).where(PreferenceGraphNode.id == node_id)
        )
        node = result.scalar_one()

        if authority_score is not None:
            node.authority_score = authority_score
        if persistence_score is not None:
            node.persistence_score = persistence_score
        if citation_count is not None:
            node.citation_count = citation_count
        if mention_count is not None:
            node.mention_count = mention_count

        node.updated_at = datetime.utcnow()
        await self.db.flush()

    # =========================================================================
    # EDGE MANAGEMENT
    # =========================================================================

    async def get_or_create_edge(
        self,
        source_node_id: UUID,
        target_node_id: UUID,
        edge_type: GraphEdgeType,
        project_id: Optional[UUID] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> PreferenceGraphEdge:
        """Get or create an edge in the preference graph."""
        result = await self.db.execute(
            select(PreferenceGraphEdge).where(
                and_(
                    PreferenceGraphEdge.source_node_id == source_node_id,
                    PreferenceGraphEdge.target_node_id == target_node_id,
                    PreferenceGraphEdge.edge_type == edge_type,
                )
            )
        )
        edge = result.scalar_one_or_none()

        if edge:
            return edge

        # Create new edge
        edge = PreferenceGraphEdge(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            project_id=project_id,
            properties=properties or {},
        )
        self.db.add(edge)
        await self.db.flush()
        return edge

    async def increment_edge(
        self,
        source_node_id: UUID,
        target_node_id: UUID,
        edge_type: GraphEdgeType,
        project_id: Optional[UUID] = None,
        weight_delta: float = 1.0,
    ) -> PreferenceGraphEdge:
        """Increment edge weight and observation count."""
        edge = await self.get_or_create_edge(
            source_node_id, target_node_id, edge_type, project_id
        )

        edge.weight += weight_delta
        edge.frequency += 1
        edge.observation_count += 1
        edge.last_observed = datetime.utcnow()
        edge.recency_score = 1.0  # Reset recency on new observation
        edge.updated_at = datetime.utcnow()

        await self.db.flush()
        return edge

    async def decay_edge_recency(
        self,
        days_old: int = 1
    ) -> int:
        """Apply recency decay to all edges. Returns count of updated edges."""
        decay_factor = self.RECENCY_DECAY ** days_old

        result = await self.db.execute(
            update(PreferenceGraphEdge)
            .values(recency_score=PreferenceGraphEdge.recency_score * decay_factor)
            .where(PreferenceGraphEdge.recency_score > 0.01)  # Don't decay tiny values
        )

        return result.rowcount

    # =========================================================================
    # GRAPH BUILDING FROM OBSERVATIONS
    # =========================================================================

    async def record_citation(
        self,
        provider: LLMProvider,
        domain: str,
        project_id: UUID,
        weight: float = 1.0,
    ) -> Tuple[PreferenceGraphNode, PreferenceGraphNode, PreferenceGraphEdge]:
        """
        Record that an LLM cited a domain.
        Creates/updates LLM node, domain node, and CITES edge.
        """
        # Get or create LLM node (global, no project)
        llm_node = await self.get_or_create_node(
            GraphNodeType.LLM,
            provider.value,
            display_name=provider.value.replace("_", " ").title(),
        )

        # Get or create domain node (project-scoped)
        domain_node = await self.get_or_create_node(
            GraphNodeType.DOMAIN,
            domain,
            project_id=project_id,
        )

        # Increment citation count on domain node
        domain_node.citation_count = (domain_node.citation_count or 0) + 1

        # Create/update CITES edge
        edge = await self.increment_edge(
            llm_node.id,
            domain_node.id,
            GraphEdgeType.CITES,
            project_id=project_id,
            weight_delta=weight,
        )

        await self.db.flush()
        return llm_node, domain_node, edge

    async def record_brand_mention(
        self,
        provider: LLMProvider,
        brand_name: str,
        project_id: UUID,
        position: Optional[int] = None,
        is_positive: bool = True,
    ) -> Tuple[PreferenceGraphNode, PreferenceGraphNode, PreferenceGraphEdge]:
        """
        Record that an LLM mentioned a brand.
        """
        # Position-based weight (earlier = higher weight)
        position_weight = 1.0
        if position is not None:
            position_weight = max(0.5, 1.0 - (position - 1) * 0.1)

        # Sentiment weight
        sentiment_weight = 1.0 if is_positive else 0.5

        weight = position_weight * sentiment_weight

        # Get or create LLM node
        llm_node = await self.get_or_create_node(
            GraphNodeType.LLM,
            provider.value,
        )

        # Get or create brand node
        brand_node = await self.get_or_create_node(
            GraphNodeType.BRAND,
            brand_name.lower(),
            project_id=project_id,
            display_name=brand_name,
        )

        # Increment mention count
        brand_node.mention_count = (brand_node.mention_count or 0) + 1

        # Create/update MENTIONS edge
        edge = await self.increment_edge(
            llm_node.id,
            brand_node.id,
            GraphEdgeType.MENTIONS,
            project_id=project_id,
            weight_delta=weight,
        )

        await self.db.flush()
        return llm_node, brand_node, edge

    async def record_brand_source_association(
        self,
        domain: str,
        brand_name: str,
        project_id: UUID,
    ) -> Tuple[PreferenceGraphNode, PreferenceGraphNode, PreferenceGraphEdge]:
        """
        Record that a brand was mentioned in context with a source.
        """
        domain_node = await self.get_or_create_node(
            GraphNodeType.DOMAIN,
            domain,
            project_id=project_id,
        )

        brand_node = await self.get_or_create_node(
            GraphNodeType.BRAND,
            brand_name.lower(),
            project_id=project_id,
            display_name=brand_name,
        )

        edge = await self.increment_edge(
            domain_node.id,
            brand_node.id,
            GraphEdgeType.ASSOCIATED,
            project_id=project_id,
        )

        await self.db.flush()
        return domain_node, brand_node, edge

    # =========================================================================
    # SOURCE AUTHORITY SCORING
    # =========================================================================

    async def calculate_source_authority(
        self,
        source_id: UUID,
        provider: LLMProvider,
        project_id: UUID,
        days: int = 30,
    ) -> SourceAuthority:
        """
        Calculate authority score for a source in a specific LLM.
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get citation statistics
        result = await self.db.execute(
            select(
                func.count(Citation.id).label("citation_count"),
                func.avg(Citation.position_in_response).label("avg_position"),
            )
            .join(LLMResponse)
            .join(LLMRun)
            .where(
                and_(
                    Citation.source_id == source_id,
                    LLMRun.provider == provider,
                    LLMRun.project_id == project_id,
                    LLMRun.created_at >= start_date,
                )
            )
        )
        stats = result.one()

        citation_count = stats[0] or 0
        avg_position = stats[1]

        # Get total runs for this provider in the project
        result = await self.db.execute(
            select(func.count(LLMRun.id)).where(
                and_(
                    LLMRun.project_id == project_id,
                    LLMRun.provider == provider,
                    LLMRun.created_at >= start_date,
                )
            )
        )
        total_runs = result.scalar() or 1

        # Calculate frequency (citations per 100 queries)
        citation_frequency = (citation_count / total_runs) * 100

        # Get or create source authority record
        result = await self.db.execute(
            select(SourceAuthority).where(
                and_(
                    SourceAuthority.source_id == source_id,
                    SourceAuthority.provider == provider,
                )
            )
        )
        authority = result.scalar_one_or_none()

        if not authority:
            authority = SourceAuthority(
                source_id=source_id,
                provider=provider,
            )
            self.db.add(authority)

        authority.citation_count = citation_count
        authority.citation_frequency = citation_frequency
        authority.position_avg = avg_position
        authority.recency_weighted_score = self._calculate_recency_weighted_score(
            citation_count, citation_frequency, avg_position
        )
        authority.last_citation = datetime.utcnow() if citation_count > 0 else authority.last_citation
        authority.updated_at = datetime.utcnow()

        await self.db.flush()
        return authority

    def _calculate_recency_weighted_score(
        self,
        count: int,
        frequency: float,
        avg_position: Optional[float],
    ) -> float:
        """Calculate a combined authority score."""
        # Base score from frequency
        freq_score = min(frequency * 2, 100)  # Cap at 100

        # Position bonus (earlier = better)
        position_bonus = 0
        if avg_position is not None:
            position_bonus = max(0, 20 - avg_position * 2)

        # Volume bonus
        volume_bonus = min(count * 0.5, 20)  # Cap at 20

        return freq_score + position_bonus + volume_bonus

    # =========================================================================
    # LLM BEHAVIOR PROFILING
    # =========================================================================

    async def update_llm_behavior_profile(
        self,
        provider: LLMProvider,
        project_id: UUID,
        days: int = 30,
    ) -> LLMBehaviorProfile:
        """
        Analyze and update the behavior profile for an LLM.
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get runs for this provider
        result = await self.db.execute(
            select(LLMRun).where(
                and_(
                    LLMRun.provider == provider,
                    LLMRun.project_id == project_id,
                    LLMRun.created_at >= start_date,
                )
            )
        )
        runs = list(result.scalars().all())

        if not runs:
            return None

        run_ids = [r.id for r in runs]

        # Get citation stats
        result = await self.db.execute(
            select(
                func.count(Citation.id).label("total_citations"),
                func.count(func.distinct(Citation.source_id)).label("unique_sources"),
            )
            .join(LLMResponse)
            .where(LLMResponse.llm_run_id.in_(run_ids))
        )
        citation_stats = result.one()

        # Get brand mention stats
        result = await self.db.execute(
            select(
                func.count(BrandMention.id).label("total_mentions"),
                func.avg(BrandMention.position_in_response).label("avg_position"),
            )
            .join(LLMResponse)
            .where(LLMResponse.llm_run_id.in_(run_ids))
        )
        mention_stats = result.one()

        # Get or create profile
        result = await self.db.execute(
            select(LLMBehaviorProfile).where(LLMBehaviorProfile.provider == provider)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            profile = LLMBehaviorProfile(provider=provider)
            self.db.add(profile)

        total_runs = len(runs)

        profile.avg_citations_per_response = (citation_stats[0] or 0) / total_runs
        profile.citation_source_diversity = (citation_stats[1] or 0) / max(citation_stats[0] or 1, 1)
        profile.avg_brands_mentioned = (mention_stats[0] or 0) / total_runs
        profile.total_runs_analyzed = total_runs
        profile.analysis_period_days = days
        profile.updated_at = datetime.utcnow()

        await self.db.flush()
        return profile

    # =========================================================================
    # GRAPH QUERIES
    # =========================================================================

    async def get_llm_preferred_sources(
        self,
        provider: LLMProvider,
        project_id: UUID,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get the top sources cited by an LLM, ranked by preference."""
        # Get LLM node
        llm_node = await self.get_node(GraphNodeType.LLM, provider.value)
        if not llm_node:
            return []

        # Get edges from this LLM
        result = await self.db.execute(
            select(PreferenceGraphEdge, PreferenceGraphNode)
            .join(PreferenceGraphNode, PreferenceGraphEdge.target_node_id == PreferenceGraphNode.id)
            .where(
                and_(
                    PreferenceGraphEdge.source_node_id == llm_node.id,
                    PreferenceGraphEdge.edge_type == GraphEdgeType.CITES,
                    PreferenceGraphEdge.project_id == project_id,
                )
            )
            .order_by(
                (PreferenceGraphEdge.weight * PreferenceGraphEdge.recency_score).desc()
            )
            .limit(limit)
        )

        sources = []
        for edge, node in result.all():
            sources.append({
                "domain": node.node_identifier,
                "display_name": node.display_name,
                "citation_count": node.citation_count,
                "weight": edge.weight,
                "recency_score": edge.recency_score,
                "effective_score": edge.weight * edge.recency_score,
                "first_observed": edge.first_observed.isoformat(),
                "last_observed": edge.last_observed.isoformat(),
            })

        return sources

    async def get_brand_llm_affinity(
        self,
        brand_name: str,
        project_id: UUID,
    ) -> Dict[str, Any]:
        """Get how well a brand is represented across different LLMs."""
        brand_node = await self.get_node(
            GraphNodeType.BRAND,
            brand_name.lower(),
            project_id,
        )

        if not brand_node:
            return {"error": "Brand not found in graph"}

        # Get all MENTIONS edges pointing to this brand
        result = await self.db.execute(
            select(PreferenceGraphEdge, PreferenceGraphNode)
            .join(PreferenceGraphNode, PreferenceGraphEdge.source_node_id == PreferenceGraphNode.id)
            .where(
                and_(
                    PreferenceGraphEdge.target_node_id == brand_node.id,
                    PreferenceGraphEdge.edge_type == GraphEdgeType.MENTIONS,
                )
            )
        )

        affinity = {}
        for edge, llm_node in result.all():
            affinity[llm_node.node_identifier] = {
                "mention_weight": edge.weight,
                "frequency": edge.frequency,
                "recency_score": edge.recency_score,
                "observation_count": edge.observation_count,
            }

        return {
            "brand": brand_name,
            "total_mentions": brand_node.mention_count,
            "persistence_score": brand_node.persistence_score,
            "llm_affinity": affinity,
        }

    async def get_source_brand_associations(
        self,
        domain: str,
        project_id: UUID,
    ) -> List[Dict[str, Any]]:
        """Get brands associated with a source."""
        domain_node = await self.get_node(
            GraphNodeType.DOMAIN,
            domain,
            project_id,
        )

        if not domain_node:
            return []

        result = await self.db.execute(
            select(PreferenceGraphEdge, PreferenceGraphNode)
            .join(PreferenceGraphNode, PreferenceGraphEdge.target_node_id == PreferenceGraphNode.id)
            .where(
                and_(
                    PreferenceGraphEdge.source_node_id == domain_node.id,
                    PreferenceGraphEdge.edge_type == GraphEdgeType.ASSOCIATED,
                )
            )
            .order_by(PreferenceGraphEdge.weight.desc())
        )

        associations = []
        for edge, brand_node in result.all():
            associations.append({
                "brand": brand_node.display_name,
                "association_strength": edge.weight,
                "co_occurrence_count": edge.frequency,
            })

        return associations

    async def find_authority_hubs(
        self,
        project_id: UUID,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Find authority hubs - domains that are heavily cited across multiple LLMs.
        """
        # Get domain nodes with highest citation counts
        result = await self.db.execute(
            select(PreferenceGraphNode)
            .where(
                and_(
                    PreferenceGraphNode.node_type == GraphNodeType.DOMAIN,
                    PreferenceGraphNode.project_id == project_id,
                )
            )
            .order_by(PreferenceGraphNode.authority_score.desc())
            .limit(limit)
        )

        hubs = []
        for node in result.scalars().all():
            # Get which LLMs cite this domain
            edge_result = await self.db.execute(
                select(PreferenceGraphEdge, PreferenceGraphNode)
                .join(PreferenceGraphNode, PreferenceGraphEdge.source_node_id == PreferenceGraphNode.id)
                .where(
                    and_(
                        PreferenceGraphEdge.target_node_id == node.id,
                        PreferenceGraphEdge.edge_type == GraphEdgeType.CITES,
                    )
                )
            )

            citing_llms = {}
            for edge, llm_node in edge_result.all():
                citing_llms[llm_node.node_identifier] = {
                    "weight": edge.weight,
                    "frequency": edge.frequency,
                }

            hubs.append({
                "domain": node.node_identifier,
                "authority_score": node.authority_score,
                "total_citations": node.citation_count,
                "citing_llms": citing_llms,
                "llm_coverage": len(citing_llms),
            })

        return hubs

    async def get_graph_stats(
        self,
        project_id: UUID,
    ) -> Dict[str, Any]:
        """Get statistics about the preference graph."""
        # Count nodes by type
        result = await self.db.execute(
            select(
                PreferenceGraphNode.node_type,
                func.count(PreferenceGraphNode.id),
            )
            .where(
                or_(
                    PreferenceGraphNode.project_id == project_id,
                    PreferenceGraphNode.project_id.is_(None),
                )
            )
            .group_by(PreferenceGraphNode.node_type)
        )
        nodes_by_type = {row[0].value: row[1] for row in result.all()}

        # Count edges by type
        result = await self.db.execute(
            select(
                PreferenceGraphEdge.edge_type,
                func.count(PreferenceGraphEdge.id),
            )
            .where(PreferenceGraphEdge.project_id == project_id)
            .group_by(PreferenceGraphEdge.edge_type)
        )
        edges_by_type = {row[0].value: row[1] for row in result.all()}

        # Total counts
        result = await self.db.execute(
            select(func.count(PreferenceGraphNode.id)).where(
                or_(
                    PreferenceGraphNode.project_id == project_id,
                    PreferenceGraphNode.project_id.is_(None),
                )
            )
        )
        total_nodes = result.scalar()

        result = await self.db.execute(
            select(func.count(PreferenceGraphEdge.id)).where(
                PreferenceGraphEdge.project_id == project_id
            )
        )
        total_edges = result.scalar()

        return {
            "project_id": str(project_id),
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "nodes_by_type": nodes_by_type,
            "edges_by_type": edges_by_type,
        }
