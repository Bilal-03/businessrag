from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.routes import chat, documents, health
from src.utils.exceptions import global_exception_handler, http_exception_handler
from fastapi.exceptions import HTTPException
from src.utils.logger import get_logger
from src.vectordb.vector_store import init_pinecone_index
from config import get_settings

logger = get_logger(__name__)
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hook."""
    logger.info("Initializing API services...")
    try:
        init_pinecone_index()
    except Exception as e:
        logger.error(f"Failed to initialize Pinecone: {str(e)}")
    yield
    # Shutdown logic (if needed) goes here

def create_app() -> FastAPI:
    app = FastAPI(title="BizGuide AI API", lifespan=lifespan)

    # CORS — lock down to actual frontend origin in production
    if settings.environment == "production":
        origins = [settings.frontend_url]
    else:
        origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    # Include routers
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(documents.router)

    return app

app = create_app()
