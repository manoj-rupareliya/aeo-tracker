"""
llmscm.com - LLM Visibility & Citation Intelligence Platform
Main FastAPI Application
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings


def _is_serverless() -> bool:
    """Check if running in serverless environment"""
    return bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Skip heavy initialization in serverless
    if not _is_serverless():
        from app.utils import init_db, close_db, close_redis
        await init_db()
        yield
        await close_db()
        await close_redis()
    else:
        yield


def create_app() -> FastAPI:
    """Factory function to create FastAPI app"""
    settings = get_settings()

    application = FastAPI(
        title="llmscm.com API",
        description="""
        LLM Visibility & Citation Intelligence Platform

        Track how multiple LLMs mention your brand, see which sources they cite,
        and measure your visibility over time.

        ## Features
        - Multi-LLM tracking (ChatGPT, Claude, Gemini, Perplexity)
        - Brand mention detection with fuzzy matching
        - Citation extraction and validation
        - Competitor comparison
        - Visibility scoring with full explainability
        - Time-series analytics
        """,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_development else "/docs",  # Enable docs for now
        redoc_url="/redoc" if settings.is_development else None,
    )

    # CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handler
    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle unexpected errors"""
        settings = get_settings()
        if settings.DEBUG:
            return JSONResponse(
                status_code=500,
                content={
                    "detail": str(exc),
                    "type": type(exc).__name__,
                },
            )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # Import and include API routes
    from app.api.routes import api_router
    application.include_router(api_router, prefix="/api/v1")

    # Import and include Admin dashboard routes
    from app.admin import admin_router
    application.include_router(admin_router, prefix="/admin", tags=["admin"])

    # Health check
    @application.get("/health")
    async def health_check():
        """Health check endpoint"""
        settings = get_settings()
        return {
            "status": "healthy",
            "version": "1.0.0",
            "environment": settings.APP_ENV,
        }

    # Root redirect
    @application.get("/")
    async def root():
        """Root endpoint"""
        settings = get_settings()
        return {
            "name": "llmscm.com API",
            "version": "1.0.0",
            "docs": "/docs" if settings.is_development else "/docs",
        }

    return application


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.is_development,
        workers=1 if settings.is_development else settings.WORKERS,
    )
