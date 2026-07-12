from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.db_models import (
    User, Group, Permission, GroupPermission, UserGroup,
    ROLE_PERMISSIONS
)
from typing import List, Set


async def get_user_permissions(db: AsyncSession, user: User) -> Set[str]:
    """
    Retorna o conjunto completo de permissões de um usuário.
    Combina: permissões do role base + permissões dos grupos extras.
    """
    permissions = set()

    # 1. Permissões do role base
    role_perms = ROLE_PERMISSIONS.get(user.role, [])
    permissions.update(role_perms)

    # 2. Permissões dos grupos extras do usuário
    for user_group in user.groups:
        group = user_group.group
        if group and group.permissions:
            for gp in group.permissions:
                if gp.permission:
                    permissions.add(gp.permission.codename)

    return permissions


async def has_permission(db: AsyncSession, user: User, permission_codename: str) -> bool:
    """Verifica se o usuário tem uma permissão específica."""
    # SuperAdmin sempre tem tudo
    if user.role == "superadmin":
        return True

    perms = await get_user_permissions(db, user)
    return permission_codename in perms


async def has_any_permission(db: AsyncSession, user: User, permission_codenames: List[str]) -> bool:
    """Verifica se o usuário tem pelo menos uma das permissões listadas."""
    if user.role == "superadmin":
        return True

    perms = await get_user_permissions(db, user)
    return bool(perms.intersection(permission_codenames))


async def get_all_permissions(db: AsyncSession) -> list:
    """Retorna todas as permissões do sistema."""
    result = await db.execute(select(Permission).order_by(Permission.categoria, Permission.codename))
    return result.scalars().all()


async def get_group_permissions(db: AsyncSession, group_id: str) -> List[str]:
    """Retorna os codenames das permissões de um grupo."""
    result = await db.execute(
        select(Permission.codename)
        .join(GroupPermission, GroupPermission.permission_id == Permission.id)
        .where(GroupPermission.group_id == group_id)
    )
    return [row[0] for row in result.all()]
