import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.db_models import User, Conversation, Message
from backend.models.schemas import (
    ChatRequest, ChatResponse, ConversationResponse,
    ConversationDetailResponse, MessageResponse,
)
from backend.middleware.auth_middleware import get_current_user, require_permission
from backend.services import rag_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
async def chat(
    request: ChatRequest,
    user: User = Depends(require_permission("chat.use")),
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint principal de chat RAG.
    Cria ou continua uma conversa.
    """
    # Criar ou buscar conversa
    if request.conversation_id:
        conv_result = await db.execute(
            select(Conversation).where(
                Conversation.id == request.conversation_id,
                Conversation.user_id == user.id,
            )
        )
        conversation = conv_result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversa não encontrada")
    else:
        # Criar nova conversa
        titulo = request.message[:50] + ("..." if len(request.message) > 50 else "")
        conversation = Conversation(user_id=user.id, titulo=titulo)
        db.add(conversation)
        await db.flush()

    # Salvar mensagem do usuário
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        conteudo=request.message,
    )
    db.add(user_msg)
    await db.flush()

    # Executar RAG
    try:
        result = await rag_service.query_rag(
            question=request.message,
            db=db,
        )
    except Exception as e:
        # Salvar erro como mensagem do assistente
        error_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            conteudo=f"Desculpe, ocorreu um erro ao processar sua pergunta: {str(e)}",
        )
        db.add(error_msg)
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))

    # Salvar resposta do assistente
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        conteudo=result["message"],
        fontes_json=result["sources"],
    )
    db.add(assistant_msg)
    await db.commit()

    return ChatResponse(
        message=result["message"],
        sources=result["sources"],
        conversation_id=conversation.id,
    )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    user: User = Depends(require_permission("chat.use")),
    db: AsyncSession = Depends(get_db),
):
    """
    Chat RAG com streaming de resposta via Server-Sent Events.
    """
    # Criar ou buscar conversa
    if request.conversation_id:
        conv_result = await db.execute(
            select(Conversation).where(
                Conversation.id == request.conversation_id,
                Conversation.user_id == user.id,
            )
        )
        conversation = conv_result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversa não encontrada")
    else:
        titulo = request.message[:50] + ("..." if len(request.message) > 50 else "")
        conversation = Conversation(user_id=user.id, titulo=titulo)
        db.add(conversation)
        await db.flush()

    # Salvar mensagem do usuário
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        conteudo=request.message,
    )
    db.add(user_msg)
    await db.flush()
    await db.commit()

    # Buscar contexto e preparar stream
    response_generator, sources = await rag_service.query_rag_stream(
        question=request.message,
        db=db,
    )

    async def event_stream():
        full_response = ""

        # Enviar fontes primeiro
        yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"

        # Enviar conversation_id
        yield f"data: {json.dumps({'type': 'conversation_id', 'data': conversation.id})}\n\n"

        # Stream de tokens com keep-alive
        import asyncio
        iterator = response_generator().__aiter__()
        while True:
            try:
                # Aguarda até 10s pelo próximo token
                token = await asyncio.wait_for(iterator.__anext__(), timeout=10.0)
                full_response += token
                yield f"data: {json.dumps({'type': 'token', 'data': token})}\n\n"
            except asyncio.TimeoutError:
                # Envia um comentário SSE para manter a conexão ativa (Cloudflare/Nginx não corta)
                yield ": keepalive\n\n"
            except StopAsyncIteration:
                break

        # Salvar resposta completa no DB
        async with db.begin():
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                conteudo=full_response,
                fontes_json=sources,
            )
            db.add(assistant_msg)

        yield f"data: {json.dumps({'type': 'done', 'data': ''})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# Conversations CRUD
# ============================================================

@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    user: User = Depends(require_permission("chat.history")),
    db: AsyncSession = Depends(get_db),
):
    """Lista as conversas do usuário logado."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.atualizado_em.desc())
    )
    conversations = result.scalars().all()

    response = []
    for conv in conversations:
        msg_count = await db.execute(
            select(func.count()).where(Message.conversation_id == conv.id)
        )
        count = msg_count.scalar() or 0
        response.append(ConversationResponse(
            id=conv.id,
            titulo=conv.titulo,
            criado_em=conv.criado_em,
            atualizado_em=conv.atualizado_em,
            message_count=count,
        ))

    return response


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    user: User = Depends(require_permission("chat.history")),
    db: AsyncSession = Depends(get_db),
):
    """Retorna uma conversa com todas as mensagens."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    messages = [
        MessageResponse(
            id=msg.id,
            role=msg.role,
            conteudo=msg.conteudo,
            fontes_json=msg.fontes_json,
            criado_em=msg.criado_em,
        )
        for msg in conversation.messages
    ]

    return ConversationDetailResponse(
        id=conversation.id,
        titulo=conversation.titulo,
        messages=messages,
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(require_permission("chat.history")),
    db: AsyncSession = Depends(get_db),
):
    """Exclui uma conversa e suas mensagens."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    await db.delete(conversation)
    await db.commit()

    return {"message": "Conversa excluída com sucesso"}
