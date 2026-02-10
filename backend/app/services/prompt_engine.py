"""
Prompt Generation Engine
Generates versioned, reproducible prompts from templates
"""

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Keyword, Prompt, PromptTemplate, Project, Brand, Competitor, PromptType
)
from app.config import INDUSTRY_CONTEXT


class PromptEngine:
    """
    Engine for generating prompts from versioned templates.
    Ensures reproducibility and auditability of all prompts.
    """

    TEMPLATES_DIR = Path(__file__).parent.parent / "prompts" / "templates"

    def __init__(self, db: AsyncSession):
        self.db = db
        self._templates_cache: Dict[str, dict] = {}

    async def load_templates_from_yaml(self, version: str = "v1") -> List[dict]:
        """Load all templates from YAML files for a specific version"""
        templates = []
        version_dir = self.TEMPLATES_DIR / version

        if not version_dir.exists():
            raise ValueError(f"Template version {version} not found")

        for yaml_file in version_dir.glob("*.yaml"):
            with open(yaml_file, "r") as f:
                data = yaml.safe_load(f)
                for template in data.get("templates", []):
                    template["version"] = data["version"]
                    template["prompt_type"] = data["type"]
                    templates.append(template)

        return templates

    async def sync_templates_to_db(self, version: str = "v1") -> int:
        """
        Sync templates from YAML files to database.
        Creates new template versions if templates have changed.
        """
        templates = await self.load_templates_from_yaml(version)
        synced = 0

        for template_data in templates:
            # Parse version
            version_parts = template_data["version"].split(".")
            major, minor, patch = int(version_parts[0]), int(version_parts[1]), int(version_parts[2])

            # Check if template exists
            result = await self.db.execute(
                select(PromptTemplate).where(
                    PromptTemplate.name == template_data["name"],
                    PromptTemplate.is_active == True
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Check if template text changed
                if existing.template_text != template_data["template"]:
                    # Deactivate old version
                    existing.is_active = False
                    # Create new version
                    new_template = PromptTemplate(
                        name=template_data["name"],
                        prompt_type=PromptType(template_data["prompt_type"]),
                        template_text=template_data["template"],
                        version_major=major,
                        version_minor=minor,
                        version_patch=patch + 1,  # Bump patch version
                        description=template_data.get("use_case"),
                        expected_output_format=template_data.get("expected_format"),
                        is_active=True,
                    )
                    self.db.add(new_template)
                    synced += 1
            else:
                # Create new template
                new_template = PromptTemplate(
                    name=template_data["name"],
                    prompt_type=PromptType(template_data["prompt_type"]),
                    template_text=template_data["template"],
                    version_major=major,
                    version_minor=minor,
                    version_patch=patch,
                    description=template_data.get("use_case"),
                    expected_output_format=template_data.get("expected_format"),
                    is_active=True,
                )
                self.db.add(new_template)
                synced += 1

        await self.db.commit()
        return synced

    async def get_active_templates(
        self,
        prompt_types: Optional[List[PromptType]] = None
    ) -> List[PromptTemplate]:
        """Get all active templates, optionally filtered by type"""
        query = select(PromptTemplate).where(PromptTemplate.is_active == True)
        if prompt_types:
            query = query.where(PromptTemplate.prompt_type.in_(prompt_types))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    def _render_template(
        self,
        template_text: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Render a template with the given context.
        Uses simple {variable} substitution.
        """
        rendered = template_text

        for key, value in context.items():
            placeholder = f"{{{key}}}"
            if placeholder in rendered:
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                rendered = rendered.replace(placeholder, str(value))

        return rendered.strip()

    def _generate_prompt_hash(
        self,
        prompt_text: str,
        template_version: str
    ) -> str:
        """Generate deterministic hash for prompt caching"""
        content = f"{prompt_text}|{template_version}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def generate_prompts_for_keyword(
        self,
        keyword: Keyword,
        prompt_types: Optional[List[PromptType]] = None,
        regenerate: bool = False
    ) -> List[Prompt]:
        """
        Generate all prompts for a keyword based on active templates.

        Args:
            keyword: The keyword to generate prompts for
            prompt_types: Optional list of prompt types to generate
            regenerate: If True, regenerate even if prompts exist

        Returns:
            List of generated Prompt objects
        """
        # Get project context
        result = await self.db.execute(
            select(Project).where(Project.id == keyword.project_id)
        )
        project = result.scalar_one()

        # Get brands
        result = await self.db.execute(
            select(Brand).where(Brand.project_id == project.id)
        )
        brands = list(result.scalars().all())
        primary_brand = next((b for b in brands if b.is_primary), brands[0] if brands else None)

        # Get competitors
        result = await self.db.execute(
            select(Competitor).where(Competitor.project_id == project.id)
        )
        competitors = list(result.scalars().all())

        # Get active templates
        templates = await self.get_active_templates(prompt_types)

        # Check existing prompts if not regenerating
        existing_hashes = set()
        if not regenerate:
            result = await self.db.execute(
                select(Prompt.prompt_hash).where(Prompt.keyword_id == keyword.id)
            )
            existing_hashes = set(row[0] for row in result.fetchall())

        generated_prompts = []

        for template in templates:
            # Build context
            context = {
                "keyword": keyword.keyword,
                "brand": primary_brand.name if primary_brand else "",
                "industry": INDUSTRY_CONTEXT.get(project.industry, project.industry),
                "competitors": ", ".join(c.name for c in competitors[:3]),  # Top 3 competitors
                "domain": project.domain,
            }

            # Add keyword-specific context if provided
            if keyword.context:
                context["keyword_context"] = keyword.context

            # Render the template
            prompt_text = self._render_template(template.template_text, context)

            # Generate hash
            prompt_hash = self._generate_prompt_hash(prompt_text, template.version)

            # Skip if already exists
            if prompt_hash in existing_hashes:
                continue

            # Create prompt
            prompt = Prompt(
                keyword_id=keyword.id,
                template_id=template.id,
                prompt_type=template.prompt_type,
                prompt_text=prompt_text,
                prompt_hash=prompt_hash,
                injected_context=context,
            )

            self.db.add(prompt)
            generated_prompts.append(prompt)

        await self.db.commit()
        return generated_prompts

    async def generate_prompts_for_project(
        self,
        project_id: str,
        keyword_ids: Optional[List[str]] = None,
        prompt_types: Optional[List[PromptType]] = None,
        regenerate: bool = False
    ) -> Dict[str, List[Prompt]]:
        """
        Generate prompts for multiple keywords in a project.

        Returns:
            Dict mapping keyword_id to list of generated prompts
        """
        # Get keywords
        query = select(Keyword).where(
            Keyword.project_id == project_id,
            Keyword.is_active == True
        )
        if keyword_ids:
            query = query.where(Keyword.id.in_(keyword_ids))

        result = await self.db.execute(query)
        keywords = list(result.scalars().all())

        results = {}
        for keyword in keywords:
            prompts = await self.generate_prompts_for_keyword(
                keyword, prompt_types, regenerate
            )
            results[str(keyword.id)] = prompts

        return results

    async def get_prompts_for_keyword(self, keyword_id: str) -> List[Prompt]:
        """Get all prompts for a keyword"""
        result = await self.db.execute(
            select(Prompt).where(Prompt.keyword_id == keyword_id)
        )
        return list(result.scalars().all())

    async def get_prompt_by_hash(self, prompt_hash: str) -> Optional[Prompt]:
        """Get a prompt by its hash"""
        result = await self.db.execute(
            select(Prompt).where(Prompt.prompt_hash == prompt_hash)
        )
        return result.scalar_one_or_none()
