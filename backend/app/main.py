"""
llmrefs.com - LLM Visibility & Citation Intelligence Platform
Main FastAPI Application
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.utils import init_db, close_db, close_redis
from app.api.routes import api_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()
    await close_redis()


app = FastAPI(
    title="llmrefs.com API",
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
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
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


# Include API routes
app.include_router(api_router, prefix="/api/v1")


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.APP_ENV,
    }


# Root redirect
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "llmrefs.com API",
        "version": "1.0.0",
        "docs": "/docs" if settings.is_development else None,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.is_development,
        workers=1 if settings.is_development else settings.WORKERS,
    )
