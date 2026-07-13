import logging
import json
import asyncio
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from backend.database import get_db
from backend.models.db_models import Document, SiteConfig
from backend.middleware.auth_middleware import get_current_user, require_permission
from backend.services import llm_service, qdrant_service, embedding_service
from backend.models.db_models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])


class SummarizeRequest(BaseModel):
    document_id: str
    focus: Optional[str] = None


class CrossAnalysisRequest(BaseModel):
    document_ids: List[str]
    topic: str


@router.post("/summarize")
async def summarize_document(
    request: SummarizeRequest,
    user: User = Depends(require_permission("documents.view")),
    db: AsyncSession = Depends(get_db),
):
    """Gera um resumo detalhado de um documento, focado em um tema se especificado."""
    # Verificar se o documento existe
    result = await db.execute(select(Document).where(Document.id == request.document_id))
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
        
    # Buscar os vetores desse documento no Qdrant
    # Como não temos uma função getAll do documento no qdrant service de forma simples, 
    # faremos uma busca por semântica caso tenha 'focus' ou pegamos chunks de amostra.
    # Outra abordagem: o Qdrant permite Scroll. Vamos simplificar buscando usando o título ou focus
    
    query_text = request.focus if request.focus else f"Resumo principal e pontos chaves do documento {document.nome}"
    query_embedding = await embedding_service.generate_embedding(query_text)
    
    # Buscar chunks relevantes (usamos um limit maior para relatórios)
    results = await qdrant_service.search_similar(
        query_vector=query_embedding,
        limit=20,
        score_threshold=0.1
    )
    
    # Filtrar apenas os chunks do documento requisitado
    doc_chunks = [r for r in results if r["payload"].get("document_id") == request.document_id]
    
    if not doc_chunks:
        raise HTTPException(status_code=400, detail="Não foi possível extrair conteúdo suficiente do documento para resumir.")
        
    # Buscar config
    config_result = await db.execute(select(SiteConfig).where(SiteConfig.id == 1))
    site_config = config_result.scalar_one_or_none()
    
    model = site_config.modelo_llm if site_config else "llama3"
    
    context_text = "\n\n---\n\n".join([
        f"[Página: {c['payload'].get('pagina', 'N/A')}]\n{c['payload'].get('conteudo', '')}"
        for c in doc_chunks
    ])
    
    prompt = f"""Você é um analista legislativo sênior. 
Abaixo estão trechos do documento "{document.nome}".

## Trechos:
{context_text}

## Tarefa:
Elabore um relatório sumarizado do documento. 
{("Dê foco especial em: " + request.focus) if request.focus else "Destaque os principais artigos, decisões ou propostas abordadas."}
Seja estruturado, usando Markdown, tópicos e formatação clara. Não invente informações que não estão no texto.
"""

    async def response_generator():
        iterator = llm_service.generate_response_stream(
            prompt=prompt,
            model=model,
            temperature=0.3,
            max_tokens=2048,
        ).__aiter__()
        
        try:
            while True:
                task = asyncio.create_task(iterator.__anext__())
                while not task.done():
                    done, pending = await asyncio.wait([task], timeout=10.0)
                    if task in pending:
                        yield ": keepalive\n\n"
                
                try:
                    token = task.result()
                    yield f"data: {json.dumps({'type': 'token', 'data': token})}\n\n"
                except StopAsyncIteration:
                    break
        except Exception as e:
            logger.error(f"Erro durante stream de relatorio: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': 'Conexão com a IA foi interrompida inesperadamente.'})}\n\n"
            
        yield f"data: {json.dumps({'type': 'done', 'data': ''})}\n\n"

    return StreamingResponse(
        response_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/cross-analysis")
async def cross_analysis(
    request: CrossAnalysisRequest,
    user: User = Depends(require_permission("documents.view")),
    db: AsyncSession = Depends(get_db),
):
    """Compara múltiplos documentos (ex: Lei antiga vs. Nova PL) sobre um tema específico."""
    if len(request.document_ids) < 2:
        raise HTTPException(status_code=400, detail="Selecione pelo menos 2 documentos para análise cruzada.")
        
    query_embedding = await embedding_service.generate_embedding(request.topic)
    
    # Buscar chunks relevantes no geral
    results = await qdrant_service.search_similar(
        query_vector=query_embedding,
        limit=30, 
        score_threshold=0.1
    )
    
    # Separar os chunks por documento
    docs_context = {}
    for r in results:
        doc_id = r["payload"].get("document_id")
        if doc_id in request.document_ids:
            if doc_id not in docs_context:
                docs_context[doc_id] = {
                    "nome": r["payload"].get("doc_nome", doc_id),
                    "chunks": []
                }
            docs_context[doc_id]["chunks"].append(f"[Página {r['payload'].get('pagina', 'N/A')}]: {r['payload'].get('conteudo', '')}")
            
    if len(docs_context) < 2:
        raise HTTPException(status_code=400, detail="Não há informações suficientes nos documentos selecionados para comparar sobre esse tópico.")
        
    # Montar contexto
    context_text = ""
    for doc_id, data in docs_context.items():
        context_text += f"\n\n### Documento: {data['nome']}\n"
        context_text += "\n---\n".join(data["chunks"][:10]) # Limita pra n estourar o context window
        
    # Buscar config
    config_result = await db.execute(select(SiteConfig).where(SiteConfig.id == 1))
    site_config = config_result.scalar_one_or_none()
    model = site_config.modelo_llm if site_config else "llama3"
    
    prompt = f"""Você é um auditor e analista legislativo.
Foi solicitada uma análise cruzada sobre o tema: "{request.topic}"

Abaixo estão trechos relevantes extraídos dos documentos selecionados:
{context_text}

## Tarefa:
Compare como o tema é tratado em cada um dos documentos.
Destaque:
1. Semelhanças.
2. Contradições ou mudanças (ex: se uma PL altera a lei anterior).
3. Conclusão da análise.

Formate a resposta em Markdown, utilizando tabelas ou bullet points quando for conveniente para facilitar a leitura.
Não mencione limitações de IA, entregue a análise diretamente.
"""

    async def response_generator():
        iterator = llm_service.generate_response_stream(
            prompt=prompt,
            model=model,
            temperature=0.3,
            max_tokens=3000,
        ).__aiter__()
        
        try:
            while True:
                task = asyncio.create_task(iterator.__anext__())
                while not task.done():
                    done, pending = await asyncio.wait([task], timeout=10.0)
                    if task in pending:
                        yield ": keepalive\n\n"
                
                try:
                    token = task.result()
                    yield f"data: {json.dumps({'type': 'token', 'data': token})}\n\n"
                except StopAsyncIteration:
                    break
        except Exception as e:
            logger.error(f"Erro durante stream de relatorio: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': 'Conexão com a IA foi interrompida inesperadamente.'})}\n\n"
            
        yield f"data: {json.dumps({'type': 'done', 'data': ''})}\n\n"

    return StreamingResponse(
        response_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
