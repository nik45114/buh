"""
FastAPI приложение
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.api import routes
from app.database.db import init_db, close_db
import logging

logger = logging.getLogger(__name__)

# Создание приложения
app = FastAPI(
    title="Accounting Bot API",
    description="API для приема данных от Bot_Claude и управления бухгалтерией ООО \"Лепта\"",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Регистрация роутов
app.include_router(routes.router, prefix="/api", tags=["api"])


@app.on_event("startup")
async def startup():
    """Действия при запуске"""
    await init_db()
    logger.info("API Server started successfully")


@app.on_event("shutdown")
async def shutdown():
    """Действия при остановке"""
    await close_db()
    logger.info("API Server stopped")


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "service": "Accounting Bot API",
        "version": "1.0.0",
        "company": settings.COMPANY_NAME,
        "inn": settings.COMPANY_INN,
        "tax_system": settings.TAX_SYSTEM,
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "accounting-bot-api"
    }


@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Обработчик 404"""
    return JSONResponse(
        status_code=404,
        content={"status": "error", "detail": "Not found"}
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Обработчик 500"""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "detail": "Internal server error"}
    )


# Для запуска напрямую через uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )
