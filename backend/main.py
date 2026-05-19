from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.game import router as game_router
from app.api.research import router as research_router
from app.api.sheets import router as sheets_router
from app.api.sql_chat import router as sql_chat_router
from app.api.routes.export_routes import router as export_router
from app.api.routes.rag_routes import router as rag_router
from app.api.routes.token_routes import router as token_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.rate_limit import RateLimitMiddleware

setup_logging()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Amzur ChatBot API — powered by Gemini + LangChain",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

upload_dir = Path(settings.UPLOAD_DIR)
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")

app.include_router(chat_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(sql_chat_router, prefix="/api")
app.include_router(sheets_router, prefix="/api")
app.include_router(research_router, prefix="/api")
app.include_router(game_router, prefix="/api")
app.include_router(export_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(token_router, prefix="/api")


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok", "version": settings.APP_VERSION}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
