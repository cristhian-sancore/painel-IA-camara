import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer, Float,
    Text, ForeignKey, UniqueConstraint, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.database import Base


def gen_uuid():
    return str(uuid.uuid4())


# ============================================================
# RBAC: Users, Groups, Permissions
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    nome = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    senha_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="user")  # superadmin, admin, user
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    groups = relationship("UserGroup", back_populates="user", lazy="selectin")
    conversations = relationship("Conversation", back_populates="user", lazy="selectin")


class Group(Base):
    __tablename__ = "groups"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    nome = Column(String(255), unique=True, nullable=False)
    descricao = Column(Text, nullable=True)
    is_builtin = Column(Boolean, default=False)
    criado_em = Column(DateTime, default=datetime.utcnow)

    # Relationships
    permissions = relationship("GroupPermission", back_populates="group", lazy="selectin")
    users = relationship("UserGroup", back_populates="group", lazy="selectin")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    codename = Column(String(100), unique=True, nullable=False, index=True)
    descricao = Column(String(255), nullable=False)
    categoria = Column(String(50), nullable=False)  # chat, documents, users, groups, dashboard, settings, llm


class GroupPermission(Base):
    __tablename__ = "group_permissions"

    group_id = Column(UUID(as_uuid=False), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(UUID(as_uuid=False), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)

    group = relationship("Group", back_populates="permissions")
    permission = relationship("Permission", lazy="selectin")


class UserGroup(Base):
    __tablename__ = "user_groups"

    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_id = Column(UUID(as_uuid=False), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)

    user = relationship("User", back_populates="groups")
    group = relationship("Group", back_populates="users", lazy="selectin")


# ============================================================
# Documents
# ============================================================

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    nome = Column(String(500), nullable=False)
    nome_original = Column(String(500), nullable=False)
    tipo = Column(String(50), nullable=False)  # pdf, docx, txt
    tamanho_bytes = Column(Integer, nullable=False)
    total_chunks = Column(Integer, default=0)
    status = Column(String(50), default="pendente")  # pendente, processando, indexado, erro
    erro_msg = Column(Text, nullable=True)
    upload_por = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    caminho_arquivo = Column(String(1000), nullable=True)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    chunks = relationship("DocumentChunk", back_populates="document", lazy="selectin", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    document_id = Column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    conteudo = Column(Text, nullable=False)
    pagina = Column(Integer, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    qdrant_point_id = Column(String(255), nullable=True)

    document = relationship("Document", back_populates="chunks")


# ============================================================
# Chat / Conversations
# ============================================================

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    titulo = Column(String(500), default="Nova conversa")
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", lazy="selectin", cascade="all, delete-orphan",
                            order_by="Message.criado_em")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    conversation_id = Column(UUID(as_uuid=False), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant
    conteudo = Column(Text, nullable=False)
    fontes_json = Column(JSON, nullable=True)  # [{doc_id, doc_nome, pagina, trecho}]
    criado_em = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


# ============================================================
# Site Config (singleton - sempre 1 registro)
# ============================================================

class SiteConfig(Base):
    __tablename__ = "site_config"

    id = Column(Integer, primary_key=True, default=1)
    nome_camara = Column(String(500), default="Câmara Municipal")
    cidade = Column(String(255), default="")
    estado = Column(String(2), default="")
    logo_path = Column(String(1000), nullable=True)
    favicon_path = Column(String(1000), nullable=True)
    cor_primaria = Column(String(7), default="#1a237e")  # Azul marinho
    cor_secundaria = Column(String(7), default="#c9a84c")  # Dourado
    cor_fundo = Column(String(7), default="#0f0f1a")  # Fundo escuro
    cor_texto = Column(String(7), default="#e0e0e0")
    system_prompt = Column(Text, default="Você é um assistente especializado em legislação municipal. Responda sempre em português brasileiro, citando as fontes dos documentos quando disponíveis. Seja preciso e objetivo.")
    modelo_llm = Column(String(100), default="llama3")
    temperatura = Column(Float, default=0.3)
    max_tokens = Column(Integer, default=2048)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================
# Permissões padrão do sistema
# ============================================================

DEFAULT_PERMISSIONS = [
    {"codename": "chat.use", "descricao": "Usar o chat RAG", "categoria": "chat"},
    {"codename": "chat.history", "descricao": "Ver histórico de conversas", "categoria": "chat"},
    {"codename": "documents.view", "descricao": "Visualizar documentos indexados", "categoria": "documents"},
    {"codename": "documents.upload", "descricao": "Fazer upload de documentos", "categoria": "documents"},
    {"codename": "documents.manage", "descricao": "Gerenciar status e ativos dos documentos", "categoria": "documents"},
    {"codename": "documents.delete", "descricao": "Remover documentos", "categoria": "documents"},
    {"codename": "users.view", "descricao": "Ver lista de usuários", "categoria": "users"},
    {"codename": "users.manage", "descricao": "Criar/editar/desativar usuários", "categoria": "users"},
    {"codename": "groups.manage", "descricao": "Criar/editar grupos e permissões", "categoria": "groups"},
    {"codename": "dashboard.view", "descricao": "Ver métricas e dashboard", "categoria": "dashboard"},
    {"codename": "settings.view", "descricao": "Ver configurações do sistema", "categoria": "settings"},
    {"codename": "settings.edit", "descricao": "Editar configurações do sistema", "categoria": "settings"},
    {"codename": "llm.configure", "descricao": "Alterar modelo, prompt, temperatura", "categoria": "llm"},
]

# Permissões de cada role built-in
ROLE_PERMISSIONS = {
    "superadmin": [p["codename"] for p in DEFAULT_PERMISSIONS],  # Tudo
    "admin": [
        "chat.use", "chat.history",
        "documents.view", "documents.upload", "documents.manage", "documents.delete",
        "users.view", "users.manage",
        "dashboard.view",
    ],
    "user": [
        "chat.use", "chat.history",
        "documents.view",
    ],
}
