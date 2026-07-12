from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# ============================================================
# Auth
# ============================================================

class LoginRequest(BaseModel):
    email: str
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class RefreshRequest(BaseModel):
    refresh_token: str


# ============================================================
# Users
# ============================================================

class UserCreate(BaseModel):
    nome: str = Field(..., min_length=2, max_length=255)
    email: str = Field(..., max_length=255)
    senha: str = Field(..., min_length=6)
    role: str = Field(default="user")
    group_ids: Optional[List[str]] = []


class UserUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[str] = None
    senha: Optional[str] = None
    role: Optional[str] = None
    ativo: Optional[bool] = None
    group_ids: Optional[List[str]] = None


class UserResponse(BaseModel):
    id: str
    nome: str
    email: str
    role: str
    ativo: bool
    criado_em: datetime
    groups: List["GroupBasicResponse"] = []
    permissions: List[str] = []

    class Config:
        from_attributes = True


# ============================================================
# Groups
# ============================================================

class GroupCreate(BaseModel):
    nome: str = Field(..., min_length=2, max_length=255)
    descricao: Optional[str] = None
    permission_codenames: List[str] = []


class GroupUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    permission_codenames: Optional[List[str]] = None


class GroupBasicResponse(BaseModel):
    id: str
    nome: str

    class Config:
        from_attributes = True


class GroupResponse(BaseModel):
    id: str
    nome: str
    descricao: Optional[str]
    is_builtin: bool
    criado_em: datetime
    permissions: List["PermissionResponse"] = []
    user_count: int = 0

    class Config:
        from_attributes = True


class PermissionResponse(BaseModel):
    id: str
    codename: str
    descricao: str
    categoria: str

    class Config:
        from_attributes = True


# ============================================================
# Documents
# ============================================================

class DocumentResponse(BaseModel):
    id: str
    nome: str
    nome_original: str
    tipo: str
    tamanho_bytes: int
    total_chunks: int
    status: str
    erro_msg: Optional[str]
    ativo: bool = True
    criado_em: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    page: int
    per_page: int


# ============================================================
# Chat
# ============================================================

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None


class SourceInfo(BaseModel):
    doc_id: str
    doc_nome: str
    pagina: Optional[int]
    trecho: str
    score: float


class ChatResponse(BaseModel):
    message: str
    sources: List[SourceInfo] = []
    conversation_id: str


class ConversationResponse(BaseModel):
    id: str
    titulo: str
    criado_em: datetime
    atualizado_em: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: str
    role: str
    conteudo: str
    fontes_json: Optional[list] = None
    criado_em: datetime

    class Config:
        from_attributes = True


class ConversationDetailResponse(BaseModel):
    id: str
    titulo: str
    messages: List[MessageResponse] = []


# ============================================================
# Site Config
# ============================================================

class SiteConfigResponse(BaseModel):
    nome_camara: str
    cidade: str
    estado: str
    logo_url: Optional[str]
    favicon_url: Optional[str]
    cor_primaria: str
    cor_secundaria: str
    cor_fundo: str
    cor_texto: str
    system_prompt: Optional[str] = None
    modelo_llm: Optional[str] = None
    temperatura: Optional[float] = None
    max_tokens: Optional[int] = None

    class Config:
        from_attributes = True


class SiteConfigUpdate(BaseModel):
    nome_camara: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    cor_primaria: Optional[str] = None
    cor_secundaria: Optional[str] = None
    cor_fundo: Optional[str] = None
    cor_texto: Optional[str] = None
    system_prompt: Optional[str] = None
    modelo_llm: Optional[str] = None
    temperatura: Optional[float] = None
    max_tokens: Optional[int] = None


# ============================================================
# Admin Dashboard
# ============================================================

class DashboardStats(BaseModel):
    total_documentos: int
    total_chunks: int
    total_usuarios: int
    total_conversas: int
    total_mensagens: int
    servicos: dict  # status de cada serviço


class HealthResponse(BaseModel):
    status: str
    services: dict
    version: str = "1.0.0"


# Resolver forward references
TokenResponse.model_rebuild()
UserResponse.model_rebuild()
GroupResponse.model_rebuild()
