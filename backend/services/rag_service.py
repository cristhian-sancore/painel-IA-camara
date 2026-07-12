import logging
from typing import List, Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.db_models import SiteConfig
from backend.services import embedding_service, qdrant_service, llm_service

logger = logging.getLogger(__name__)


def build_rag_prompt(question: str, context_chunks: List[dict], system_prompt: str = None) -> str:
    """
    Monta o prompt RAG com o contexto dos documentos relevantes.
    """
    if not system_prompt:
        system_prompt = (
            "Você é um assistente especializado em legislação municipal. "
            "Responda sempre em português brasileiro, citando as fontes dos documentos quando disponíveis. "
            "Seja preciso e objetivo."
        )

    context_text = "\n\n---\n\n".join([
        f"[Documento: {c['payload'].get('doc_nome', 'N/A')} | Página: {c['payload'].get('pagina', 'N/A')}]\n{c['payload'].get('conteudo', '')}"
        for c in context_chunks
    ])

    prompt = f"""{system_prompt}

## Contexto dos Documentos

{context_text}

## Pergunta do Usuário

{question}

## Instruções
- Responda baseando-se EXCLUSIVAMENTE no contexto acima.
- Se a informação não estiver no contexto, diga que não encontrou informação relevante nos documentos disponíveis.
- Cite quais documentos e páginas embasam sua resposta.
- Responda em português brasileiro de forma clara e objetiva."""

    return prompt


async def query_rag(
    question: str,
    db: AsyncSession,
    top_k: int = 5,
) -> dict:
    """
    Pipeline RAG completo (não-streaming):
    1. Gera embedding da pergunta
    2. Busca chunks similares no Qdrant
    3. Monta prompt com contexto
    4. Gera resposta com o LLM
    """
    # Buscar config do site para system_prompt e modelo
    config_result = await db.execute(select(SiteConfig).where(SiteConfig.id == 1))
    site_config = config_result.scalar_one_or_none()

    model = site_config.modelo_llm if site_config else "llama3"
    system_prompt = site_config.system_prompt if site_config else None
    temperature = site_config.temperatura if site_config else 0.3
    max_tokens = site_config.max_tokens if site_config else 2048

    # 1. Gerar embedding da pergunta
    query_embedding = await embedding_service.generate_embedding(question)

    # 2. Buscar chunks similares
    results = await qdrant_service.search_similar(
        query_vector=query_embedding,
        limit=top_k,
    )

    # 3. Montar prompt
    prompt = build_rag_prompt(question, results, system_prompt)

    # 4. Gerar resposta
    response_text = await llm_service.generate_response(
        prompt=prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # 5. Montar fontes
    sources = []
    for r in results:
        sources.append({
            "doc_id": r["payload"].get("document_id", ""),
            "doc_nome": r["payload"].get("doc_nome", ""),
            "pagina": r["payload"].get("pagina"),
            "trecho": r["payload"].get("conteudo", "")[:200] + "...",
            "score": round(r["score"], 4),
        })

    return {
        "message": response_text,
        "sources": sources,
    }


async def query_rag_stream(
    question: str,
    db: AsyncSession,
    top_k: int = 5,
) -> tuple:
    """
    Pipeline RAG com streaming.
    Retorna (generator, sources) para streaming da resposta.
    """
    # Buscar config
    config_result = await db.execute(select(SiteConfig).where(SiteConfig.id == 1))
    site_config = config_result.scalar_one_or_none()

    model = site_config.modelo_llm if site_config else "llama3"
    system_prompt = site_config.system_prompt if site_config else None
    temperature = site_config.temperatura if site_config else 0.3
    max_tokens = site_config.max_tokens if site_config else 2048

    # 1. Embedding
    query_embedding = await embedding_service.generate_embedding(question)

    # 2. Buscar
    results = await qdrant_service.search_similar(
        query_vector=query_embedding,
        limit=top_k,
    )

    # 3. Prompt
    prompt = build_rag_prompt(question, results, system_prompt)

    # 4. Montar fontes
    sources = []
    for r in results:
        sources.append({
            "doc_id": r["payload"].get("document_id", ""),
            "doc_nome": r["payload"].get("doc_nome", ""),
            "pagina": r["payload"].get("pagina"),
            "trecho": r["payload"].get("conteudo", "")[:200] + "...",
            "score": round(r["score"], 4),
        })

    # 5. Stream generator
    async def response_generator():
        async for token in llm_service.generate_response_stream(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield token

    return response_generator, sources
