import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.db_models import User, SiteConfig
from backend.models.schemas import SiteConfigResponse, SiteConfigUpdate
from backend.middleware.auth_middleware import require_permission, get_current_user
from backend.services import llm_service

router = APIRouter(prefix="/api/settings", tags=["settings"])

UPLOAD_DIR = "/app/uploads"


@router.get("/public", response_model=SiteConfigResponse)
async def get_public_config(db: AsyncSession = Depends(get_db)):
    """
    Retorna configurações públicas do site (sem auth).
    Usado pelo frontend para carregar branding.
    """
    result = await db.execute(select(SiteConfig).where(SiteConfig.id == 1))
    config = result.scalar_one_or_none()

    if not config:
        return SiteConfigResponse(
            nome_camara="Câmara Municipal",
            cidade="",
            estado="",
            logo_url=None,
            favicon_url=None,
            cor_primaria="#1a237e",
            cor_secundaria="#c9a84c",
            cor_fundo="#0f0f1a",
            cor_texto="#e0e0e0",
        )

    return SiteConfigResponse(
        nome_camara=config.nome_camara,
        cidade=config.cidade,
        estado=config.estado,
        logo_url=f"/api/settings/logo" if config.logo_path else None,
        favicon_url=f"/api/settings/favicon" if config.favicon_path else None,
        cor_primaria=config.cor_primaria,
        cor_secundaria=config.cor_secundaria,
        cor_fundo=config.cor_fundo,
        cor_texto=config.cor_texto,
    )


@router.get("", response_model=SiteConfigResponse)
async def get_config(
    user: User = Depends(require_permission("settings.view")),
    db: AsyncSession = Depends(get_db),
):
    """Retorna todas as configurações do site (inclui LLM config)."""
    result = await db.execute(select(SiteConfig).where(SiteConfig.id == 1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configurações não encontradas")

    return SiteConfigResponse(
        nome_camara=config.nome_camara,
        cidade=config.cidade,
        estado=config.estado,
        logo_url=f"/api/settings/logo" if config.logo_path else None,
        favicon_url=f"/api/settings/favicon" if config.favicon_path else None,
        cor_primaria=config.cor_primaria,
        cor_secundaria=config.cor_secundaria,
        cor_fundo=config.cor_fundo,
        cor_texto=config.cor_texto,
        system_prompt=config.system_prompt,
        modelo_llm=config.modelo_llm,
        temperatura=config.temperatura,
        max_tokens=config.max_tokens,
    )


@router.put("", response_model=SiteConfigResponse)
async def update_config(
    request: SiteConfigUpdate,
    user: User = Depends(require_permission("settings.edit")),
    db: AsyncSession = Depends(get_db),
):
    """Atualiza configurações do site."""
    result = await db.execute(select(SiteConfig).where(SiteConfig.id == 1))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configurações não encontradas")

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(config, key):
            setattr(config, key, value)

    await db.commit()
    await db.refresh(config)

    return SiteConfigResponse(
        nome_camara=config.nome_camara,
        cidade=config.cidade,
        estado=config.estado,
        logo_url=f"/api/settings/logo" if config.logo_path else None,
        favicon_url=f"/api/settings/favicon" if config.favicon_path else None,
        cor_primaria=config.cor_primaria,
        cor_secundaria=config.cor_secundaria,
        cor_fundo=config.cor_fundo,
        cor_texto=config.cor_texto,
        system_prompt=config.system_prompt,
        modelo_llm=config.modelo_llm,
        temperatura=config.temperatura,
        max_tokens=config.max_tokens,
    )


@router.post("/logo")
async def upload_logo(
    file: UploadFile = File(...),
    user: User = Depends(require_permission("settings.edit")),
    db: AsyncSession = Depends(get_db),
):
    """Upload do logo da câmara."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Apenas imagens são aceitas")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "png"
    file_name = f"logo_{uuid.uuid4().hex[:8]}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Atualizar config
    result = await db.execute(select(SiteConfig).where(SiteConfig.id == 1))
    config = result.scalar_one_or_none()
    if config:
        # Remover logo antigo
        if config.logo_path and os.path.exists(config.logo_path):
            os.remove(config.logo_path)
        config.logo_path = file_path
        await db.commit()

    return {"message": "Logo atualizado", "url": "/api/settings/logo"}


@router.post("/favicon")
async def upload_favicon(
    file: UploadFile = File(...),
    user: User = Depends(require_permission("settings.edit")),
    db: AsyncSession = Depends(get_db),
):
    """Upload do favicon."""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "ico"
    file_name = f"favicon_{uuid.uuid4().hex[:8]}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    result = await db.execute(select(SiteConfig).where(SiteConfig.id == 1))
    config = result.scalar_one_or_none()
    if config:
        if config.favicon_path and os.path.exists(config.favicon_path):
            os.remove(config.favicon_path)
        config.favicon_path = file_path
        await db.commit()

    return {"message": "Favicon atualizado", "url": "/api/settings/favicon"}


@router.get("/logo")
async def get_logo(db: AsyncSession = Depends(get_db)):
    """Retorna o arquivo do logo."""
    result = await db.execute(select(SiteConfig).where(SiteConfig.id == 1))
    config = result.scalar_one_or_none()

    if not config or not config.logo_path or not os.path.exists(config.logo_path):
        raise HTTPException(status_code=404, detail="Logo não encontrado")

    return FileResponse(config.logo_path)


@router.get("/favicon")
async def get_favicon(db: AsyncSession = Depends(get_db)):
    """Retorna o arquivo do favicon."""
    result = await db.execute(select(SiteConfig).where(SiteConfig.id == 1))
    config = result.scalar_one_or_none()

    if not config or not config.favicon_path or not os.path.exists(config.favicon_path):
        raise HTTPException(status_code=404, detail="Favicon não encontrado")

    return FileResponse(config.favicon_path)


@router.get("/models")
async def list_ollama_models(
    user: User = Depends(require_permission("llm.configure")),
):
    """Lista os modelos disponíveis no Ollama."""
    models = await llm_service.list_models()
    return {"models": models}
