import httpx
import logging
from typing import List
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def generate_embedding(text: str, model: str = None) -> List[float]:
    """
    Gera embedding de um texto usando Ollama.
    Retorna vetor de floats.
    """
    model = model or settings.embedding_model
    url = f"{settings.ollama_url}/api/embeddings"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json={
            "model": model,
            "prompt": text,
        })
        response.raise_for_status()
        data = response.json()
        return data.get("embedding", [])


async def generate_embeddings_batch(texts: List[str], model: str = None) -> List[List[float]]:
    """
    Gera embeddings para múltiplos textos.
    Processa sequencialmente para não sobrecarregar o Ollama.
    """
    embeddings = []
    for text in texts:
        emb = await generate_embedding(text, model)
        embeddings.append(emb)
    return embeddings


async def get_embedding_dimension(model: str = None) -> int:
    """
    Descobre a dimensão do vetor de embedding.
    Gera um embedding de teste e retorna o tamanho.
    """
    model = model or settings.embedding_model
    try:
        emb = await generate_embedding("teste", model)
        return len(emb)
    except Exception as e:
        logger.error(f"Erro ao obter dimensão do embedding: {e}")
        return 768  # fallback padrão para nomic-embed-text
