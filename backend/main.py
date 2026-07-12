import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import select

from backend.config import get_settings
from backend.database import init_db, async_session
from backend.models.db_models import (
    User, Group, Permission, GroupPermission,
    SiteConfig, DEFAULT_PERMISSIONS, ROLE_PERMISSIONS,
)
from backend.middleware.auth_middleware import hash_password

from backend.routes import auth, chat, documents, admin, users, groups, settings as settings_routes, reports

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app_settings = get_settings()


async def seed_database():
    """
    Popula o banco com dados iniciais:
    - Permissões padrão
    - Grupos built-in (superadmin, admin, user) com permissões
    - Usuário SuperAdmin
    - Configuração padrão do site
    """
    async with async_session() as db:
        # 1. Criar permissões
        for perm_data in DEFAULT_PERMISSIONS:
            existing = await db.execute(
                select(Permission).where(Permission.codename == perm_data["codename"])
            )
            if not existing.scalar_one_or_none():
                db.add(Permission(**perm_data))

        await db.commit()

        # 2. Criar grupos built-in
        for role_name, perm_codenames in ROLE_PERMISSIONS.items():
            existing = await db.execute(
                select(Group).where(Group.nome == role_name)
            )
            group = existing.scalar_one_or_none()

            if not group:
                group = Group(nome=role_name, descricao=f"Grupo padrão: {role_name}", is_builtin=True)
                db.add(group)
                await db.flush()

                # Atribuir permissões ao grupo
                for codename in perm_codenames:
                    perm_result = await db.execute(
                        select(Permission).where(Permission.codename == codename)
                    )
                    perm = perm_result.scalar_one_or_none()
                    if perm:
                        db.add(GroupPermission(group_id=group.id, permission_id=perm.id))

        await db.commit()

        # 3. Criar SuperAdmin se não existe
        existing_admin = await db.execute(
            select(User).where(User.email == app_settings.superadmin_email)
        )
        if not existing_admin.scalar_one_or_none():
            superadmin = User(
                nome=app_settings.superadmin_nome,
                email=app_settings.superadmin_email,
                senha_hash=hash_password(app_settings.superadmin_password),
                role="superadmin",
                ativo=True,
            )
            db.add(superadmin)
            await db.commit()
            logger.info(f"SuperAdmin criado: {app_settings.superadmin_email}")

        # 4. Criar config do site se não existe
        existing_config = await db.execute(
            select(SiteConfig).where(SiteConfig.id == 1)
        )
        if not existing_config.scalar_one_or_none():
            config = SiteConfig(id=1)
            db.add(config)
            await db.commit()
            logger.info("Configuração padrão do site criada")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle: executa na inicialização e encerramento."""
    logger.info("🚀 Iniciando Painel RAG - Câmara de Vereadores")

    # Criar tabelas
    await init_db()
    logger.info("✅ Tabelas criadas/verificadas")

    # Seed
    await seed_database()
    logger.info("✅ Dados iniciais populados")

    yield

    logger.info("🛑 Encerrando Painel RAG")


# ============================================================
# App FastAPI
# ============================================================

app = FastAPI(
    title="Painel RAG - Câmara de Vereadores",
    description="Sistema de consulta inteligente a documentos legislativos",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas API
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(admin.router)
app.include_router(users.router)
app.include_router(groups.router)
app.include_router(settings_routes.router)
app.include_router(reports.router)


# Health Check
@app.get("/api/health")
async def health_check():
    from backend.services import llm_service, qdrant_service
    from backend.models.schemas import HealthResponse

    ollama_ok = await llm_service.check_ollama_health()
    qdrant_ok = await qdrant_service.check_qdrant_health()

    return HealthResponse(
        status="ok" if (ollama_ok and qdrant_ok) else "degraded",
        services={
            "ollama": "online" if ollama_ok else "offline",
            "qdrant": "online" if qdrant_ok else "offline",
            "postgresql": "online",
        },
        version="1.0.0",
    )


# Servir frontend como arquivos estáticos
app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")
app.mount("/css", StaticFiles(directory="frontend/css"), name="css")
app.mount("/js", StaticFiles(directory="frontend/js"), name="js")


# SPA fallback - todas as rotas não-API servem o index.html
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """Serve o frontend SPA. Qualquer rota que não seja /api retorna index.html."""
    return FileResponse("frontend/index.html")
