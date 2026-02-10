"""
API Routes
"""

from fastapi import APIRouter

from .auth import router as auth_router
from .projects import router as projects_router
from .keywords import router as keywords_router
from .prompts import router as prompts_router
from .llm import router as llm_router
from .analysis import router as analysis_router
from .dashboard import router as dashboard_router
from .audit import router as audit_router
from .drift import router as drift_router
from .graph import router as graph_router
from .recommendations import router as recommendations_router
from .saiv import router as saiv_router
from .cost import router as cost_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(projects_router, prefix="/projects", tags=["Projects"])
api_router.include_router(keywords_router, prefix="/keywords", tags=["Keywords"])
api_router.include_router(prompts_router, prefix="/prompts", tags=["Prompts"])
api_router.include_router(llm_router, prefix="/llm", tags=["LLM Execution"])
api_router.include_router(analysis_router, prefix="/analysis", tags=["Analysis"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(audit_router, prefix="/audit", tags=["Trust & Audit"])
api_router.include_router(drift_router, prefix="/drift", tags=["Drift Detection"])
api_router.include_router(graph_router, prefix="/graph", tags=["Preference Graph"])
api_router.include_router(recommendations_router, prefix="/recommendations", tags=["GEO Recommendations"])
api_router.include_router(saiv_router, prefix="/saiv", tags=["Share of AI Voice"])
api_router.include_router(cost_router, prefix="/cost", tags=["Cost Governance"])
