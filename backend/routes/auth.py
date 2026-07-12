from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.db_models import User
from backend.models.schemas import LoginRequest, TokenResponse, RefreshRequest, UserResponse
from backend.middleware.auth_middleware import (
    verify_password, create_access_token, create_refresh_token,
    decode_token, get_current_user,
)
from backend.services.permission_service import get_user_permissions

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Autenticação por email e senha."""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.senha, user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
        )

    if not user.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário desativado. Contate o administrador.",
        )

    # Gerar tokens
    token_data = {"sub": user.id, "email": user.email, "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Buscar permissões
    permissions = await get_user_permissions(db, user)

    # Montar grupos
    groups = []
    for ug in user.groups:
        if ug.group:
            groups.append({"id": ug.group.id, "nome": ug.group.nome})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse(
            id=user.id,
            nome=user.nome,
            email=user.email,
            role=user.role,
            ativo=user.ativo,
            criado_em=user.criado_em,
            groups=groups,
            permissions=list(permissions),
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Renova o access token usando o refresh token."""
    payload = decode_token(request.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresh inválido",
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.ativo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado ou desativado",
        )

    token_data = {"sub": user.id, "email": user.email, "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    permissions = await get_user_permissions(db, user)
    groups = []
    for ug in user.groups:
        if ug.group:
            groups.append({"id": ug.group.id, "nome": ug.group.nome})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse(
            id=user.id,
            nome=user.nome,
            email=user.email,
            role=user.role,
            ativo=user.ativo,
            criado_em=user.criado_em,
            groups=groups,
            permissions=list(permissions),
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna os dados do usuário logado."""
    permissions = await get_user_permissions(db, user)
    groups = []
    for ug in user.groups:
        if ug.group:
            groups.append({"id": ug.group.id, "nome": ug.group.nome})

    return UserResponse(
        id=user.id,
        nome=user.nome,
        email=user.email,
        role=user.role,
        ativo=user.ativo,
        criado_em=user.criado_em,
        groups=groups,
        permissions=list(permissions),
    )
