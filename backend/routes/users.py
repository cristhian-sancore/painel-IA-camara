from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.db_models import User, UserGroup, Group
from backend.models.schemas import UserCreate, UserUpdate, UserResponse
from backend.middleware.auth_middleware import (
    require_permission, get_current_user, hash_password,
)
from backend.services.permission_service import get_user_permissions

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    user: User = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    """Lista todos os usuários."""
    result = await db.execute(select(User).order_by(User.criado_em.desc()))
    users = result.scalars().all()

    response = []
    for u in users:
        perms = await get_user_permissions(db, u)
        groups = [{"id": ug.group.id, "nome": ug.group.nome} for ug in u.groups if ug.group]
        response.append(UserResponse(
            id=u.id,
            nome=u.nome,
            email=u.email,
            role=u.role,
            ativo=u.ativo,
            criado_em=u.criado_em,
            groups=groups,
            permissions=list(perms),
        ))

    return response


@router.post("", response_model=UserResponse)
async def create_user(
    request: UserCreate,
    user: User = Depends(require_permission("users.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Cria um novo usuário."""
    # Verificar email duplicado
    existing = await db.execute(select(User).where(User.email == request.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    # Não permitir criar superadmin via API (exceto se já é superadmin)
    if request.role == "superadmin" and user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Apenas superadmin pode criar outro superadmin")

    new_user = User(
        nome=request.nome,
        email=request.email,
        senha_hash=hash_password(request.senha),
        role=request.role,
    )
    db.add(new_user)
    await db.flush()

    # Atribuir grupos
    if request.group_ids:
        for gid in request.group_ids:
            group_result = await db.execute(select(Group).where(Group.id == gid))
            group = group_result.scalar_one_or_none()
            if group:
                db.add(UserGroup(user_id=new_user.id, group_id=gid))

    await db.commit()
    await db.refresh(new_user)

    perms = await get_user_permissions(db, new_user)
    groups = [{"id": ug.group.id, "nome": ug.group.nome} for ug in new_user.groups if ug.group]

    return UserResponse(
        id=new_user.id,
        nome=new_user.nome,
        email=new_user.email,
        role=new_user.role,
        ativo=new_user.ativo,
        criado_em=new_user.criado_em,
        groups=groups,
        permissions=list(perms),
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    request: UserUpdate,
    current_user: User = Depends(require_permission("users.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Atualiza um usuário existente."""
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Proteger superadmin de ser rebaixado por admin
    if target_user.role == "superadmin" and current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Não é possível editar superadmin")

    if request.nome is not None:
        target_user.nome = request.nome
    if request.email is not None:
        # Verificar duplicado
        existing = await db.execute(
            select(User).where(User.email == request.email, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email já cadastrado")
        target_user.email = request.email
    if request.senha is not None:
        target_user.senha_hash = hash_password(request.senha)
    if request.role is not None:
        if request.role == "superadmin" and current_user.role != "superadmin":
            raise HTTPException(status_code=403, detail="Apenas superadmin pode promover a superadmin")
        target_user.role = request.role
    if request.ativo is not None:
        target_user.ativo = request.ativo

    # Atualizar grupos
    if request.group_ids is not None:
        # Remover grupos atuais
        existing_groups = await db.execute(
            select(UserGroup).where(UserGroup.user_id == user_id)
        )
        for ug in existing_groups.scalars().all():
            await db.delete(ug)

        # Adicionar novos
        for gid in request.group_ids:
            db.add(UserGroup(user_id=user_id, group_id=gid))

    await db.commit()
    await db.refresh(target_user)

    perms = await get_user_permissions(db, target_user)
    groups = [{"id": ug.group.id, "nome": ug.group.nome} for ug in target_user.groups if ug.group]

    return UserResponse(
        id=target_user.id,
        nome=target_user.nome,
        email=target_user.email,
        role=target_user.role,
        ativo=target_user.ativo,
        criado_em=target_user.criado_em,
        groups=groups,
        permissions=list(perms),
    )


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(require_permission("users.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Desativa um usuário (soft delete)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Não é possível desativar a si mesmo")

    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if target_user.role == "superadmin" and current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Não é possível desativar superadmin")

    target_user.ativo = False
    await db.commit()

    return {"message": "Usuário desativado com sucesso"}
