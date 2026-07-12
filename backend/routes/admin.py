from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.db_models import User, Document, Conversation, Message, DocumentChunk
from backend.models.schemas import DashboardStats
from backend.middleware.auth_middleware import require_permission
from backend.services import llm_service, qdrant_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard(
    user: User = Depends(require_permission("dashboard.view")),
    db: AsyncSession = Depends(get_db),
):
    """Retorna métricas do dashboard."""
    # Contagens
    docs_result = await db.execute(select(func.count()).select_from(Document))
    total_docs = docs_result.scalar() or 0

    chunks_result = await db.execute(select(func.count()).select_from(DocumentChunk))
    total_chunks = chunks_result.scalar() or 0

    users_result = await db.execute(select(func.count()).select_from(User).where(User.ativo == True))
    total_users = users_result.scalar() or 0

    convs_result = await db.execute(select(func.count()).select_from(Conversation))
    total_convs = convs_result.scalar() or 0

    msgs_result = await db.execute(select(func.count()).select_from(Message))
    total_msgs = msgs_result.scalar() or 0

    # Status dos serviços
    ollama_ok = await llm_service.check_ollama_health()
    qdrant_ok = await qdrant_service.check_qdrant_health()

    servicos = {
        "ollama": {"status": "online" if ollama_ok else "offline"},
        "qdrant": {"status": "online" if qdrant_ok else "offline"},
        "postgresql": {"status": "online"},  # Se chegou aqui, está ok
    }

    # Info extra do Qdrant
    if qdrant_ok:
        qdrant_info = await qdrant_service.get_collection_info()
        servicos["qdrant"].update(qdrant_info)

    # Modelos disponíveis no Ollama
    if ollama_ok:
        models = await llm_service.list_models()
        servicos["ollama"]["models"] = models

    return DashboardStats(
        total_documentos=total_docs,
        total_chunks=total_chunks,
        total_usuarios=total_users,
        total_conversas=total_convs,
        total_mensagens=total_msgs,
        servicos=servicos,
    )
