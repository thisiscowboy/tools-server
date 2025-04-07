from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from app.api import filesystem, memory, git, scraper, documents
from app.utils.config import get_config

app = FastAPI(
    title="othertales System Tools",
    version="1.0.0",
    description="A unified server providing filesystem, memory, git, web scraping, and document management tools for LLMs via OpenWebUI.",
)
# Configure CORS specifically for Open WebUI compatibility
origins = [
    # In production, remove the wildcard "*" and list only trusted domains
    # "*",  # Too permissive for production
    "https://ai.othertales.co",
    "https://legal.othertales.co",
    "https://mixture.othertales.co",
    # Add more specific domains as needed
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
    allow_headers=["*"],
    expose_headers=["Content-Length"],
    max_age=600,  # Cache CORS preflight requests
)
# Include routers with well-defined tags for better OpenAPI organization
app.include_router(filesystem.router, prefix="/fs", tags=["Filesystem"])
app.include_router(memory.router, prefix="/memory", tags=["Memory"])
app.include_router(git.router, prefix="/git", tags=["Git"])
app.include_router(scraper.router, prefix="/scraper", tags=["Web Scraper"])
app.include_router(documents.router, prefix="/docs", tags=["Document Management"])


# Custom OpenAPI schema generator optimized for Open WebUI
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Unified Tools Server",
        version=app.version,
        description="Document storage and retrieval system with Git versioning, knowledge graph, and web scraping capabilities.",
        routes=app.routes,
    )
    # Add tool metadata for Open WebUI
    openapi_schema["info"]["x-logo"] = {
        "url": "https://cdn-icons-png.flaticon.com/512/8728/8728086.png"
    }
    # Add toolkit info for better Open WebUI integration
    openapi_schema["info"]["x-openwebui-toolkit"] = {
        "category": "document-management",
        "capabilities": ["document-storage", "web-scraping", "git-versioning", "memory"],
        "auth_required": False,
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Set custom OpenAPI schema generator
app.openapi = custom_openapi


@app.get("/")
async def root():
    return {
        "message": "Unified Tools Server API",
        "services": ["filesystem", "memory", "git", "scraper", "documents"],
        "version": "1.0.0",
        "openapi_url": "/openapi.json",
    }


if __name__ == "__main__":
    import uvicorn

    config = get_config()
    uvicorn.run(
        "main:app", host=config.server_host, port=config.server_port, reload=config.dev_mode
    )
