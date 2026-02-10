"""
Vercel Serverless Entry Point for llmrefs.com API
Using Mangum for ASGI to AWS Lambda adapter
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

app = FastAPI(
    title="llmrefs.com API",
    description="LLM Visibility & Citation Intelligence Platform",
    version="1.0.0",
    docs_url="/docs",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "name": "llmrefs.com API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": "production"
    }

# Mangum handler for serverless
handler = Mangum(app, lifespan="off")
