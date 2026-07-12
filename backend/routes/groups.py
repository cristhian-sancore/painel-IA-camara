from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.db_models import Group, Permission, GroupPermission, UserGroup, User
from backend.models.schemas import (
    GroupCreate, GroupUpdate, GroupResponse, PermissionResponse,
)
from backend.middleware.auth_middleware import require_permission
from backend.services.permission_service import get_all_permissions

router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    user: User = Depends(require_permission("groups.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Lista todas as permissões disponíveis no sistema."""
    permissions = await get_all_permissions(db)
    return [PermissionResponse.model_validate(p) for p in permissions]


@router.get("", response_model=list[GroupResponse])
async def list_groups(
    user: User = Depends(require_permission("groups.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Lista todos os grupos."""
    result = await db.execute(select(Group).order_by(Group.is_builtin.desc(), Group.nome))
    groups = result.scalars().all()

    response = []
    for g in groups:
        # Contar usuários
        user_count_result = await db.execute(
            select(func.count()).where(UserGroup.group_id == g.id)
        )
        user_count = user_count_result.scalar() or 0

        # Permissões
        perms = []
        for gp in g.permissions:
            if gp.permission:
                perms.append(PermissionResponse.model_validate(gp.permission))

        response.append(GroupResponse(
            id=g.id,
            nome=g.nome,
            descricao=g.descricao,
            is_builtin=g.is_builtin,
            criado_em=g.criado_em,
            permissions=perms,
            user_count=user_count,
        ))

    return response


@router.post("", response_model=GroupResponse)
async def create_group(
    request: GroupCreate,
    user: User = Depends(require_permission("groups.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Cria um novo grupo personalizado."""
    # Verificar nome duplicado
    existing = await db.execute(select(Group).where(Group.nome == request.nome))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Já existe um grupo com esse nome")

    group = Group(
        nome=request.nome,
        descricao=request.descricao,
        is_builtin=False,
    )
    db.add(group)
    await db.flush()

    # Atribuir permissões
    if request.permission_codenames:
        for codename in request.permission_codenames:
            perm_result = await db.execute(
                select(Permission).where(Permission.codename == codename)
            )
            perm = perm_result.scalar_one_or_none()
            if perm:
                db.add(GroupPermission(group_id=group.id, permission_id=perm.id))

    await db.commit()
    await db.refresh(group)

    perms = []
    for gp in group.permissions:
        if gp.permission:
            perms.append(PermissionResponse.model_validate(gp.permission))

    return GroupResponse(
        id=group.id,
        nome=group.nome,
        descricao=group.descricao,
        is_builtin=group.is_builtin,
        criado_em=group.criado_em,
        permissions=perms,
        user_count=0,
    )


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: str,
    request: GroupUpdate,
    user: User = Depends(require_permission("groups.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Atualiza um grupo (apenas personalizados)."""
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")

    if group.is_builtin:
        raise HTTPException(status_code=400, detail="Grupos padrão não podem ser editados")

    if request.nome is not None:
        existing = await db.execute(
            select(Group).where(Group.nome == request.nome, Group.id != group_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Já existe um grupo com esse nome")
        group.nome = request.nome

    if request.descricao is not None:
        group.descricao = request.descricao

    # Atualizar permissões
    if request.permission_codenames is not None:
        # Remover permissões atuais
        existing_gps = await db.execute(
            select(GroupPermission).where(GroupPermission.group_id == group_id)
        )
        for gp in existing_gps.scalars().all():
            await db.delete(gp)

        # Adicionar novas
        for codename in request.permission_codenames:
            perm_result = await db.execute(
                select(Permission).where(Permission.codename == codename)
            )
            perm = perm_result.scalar_one_or_none()
            if perm:
                db.add(GroupPermission(group_id=group_id, permission_id=perm.id))

    await db.commit()
    await db.refresh(group)

    perms = []
    for gp in group.permissions:
        if gp.permission:
            perms.append(PermissionResponse.model_validate(gp.permission))

    user_count_result = await db.execute(
        select(func.count()).where(UserGroup.group_id == group_id)
    )
    user_count = user_count_result.scalar() or 0

    return GroupResponse(
        id=group.id,
        nome=group.nome,
        descricao=group.descricao,
        is_builtin=group.is_builtin,
        criado_em=group.criado_em,
        permissions=perms,
        user_count=user_count,
    )


@router.delete("/{group_id}")
async def delete_group(
    group_id: str,
    user: User = Depends(require_permission("groups.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Exclui um grupo personalizado."""
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")

    if group.is_builtin:
        raise HTTPException(status_code=400, detail="Grupos padrão não podem ser excluídos")

    await db.delete(group)
    await db.commit()

    return {"message": "Grupo excluído com sucesso"}
