import logging
import uuid
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def get_qdrant_client() -> QdrantClient:
    """Retorna cliente Qdrant."""
    return QdrantClient(url=settings.qdrant_url)


async def ensure_collection(dimension: int = 768):
    """
    Garante que a collection existe no Qdrant.
    Cria se não existir.
    """
    client = get_qdrant_client()
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if settings.qdrant_collection not in collection_names:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=qmodels.VectorParams(
                size=dimension,
                distance=qmodels.Distance.COSINE,
            ),
        )
        logger.info(f"Collection '{settings.qdrant_collection}' criada com dimensão {dimension}")


async def upsert_vectors(
    vectors: List[List[float]],
    payloads: List[dict],
    ids: Optional[List[str]] = None,
):
    """
    Insere ou atualiza vetores no Qdrant.
    """
    client = get_qdrant_client()

    if ids is None:
        ids = [str(uuid.uuid4()) for _ in vectors]

    points = [
        qmodels.PointStruct(
            id=point_id,
            vector=vector,
            payload=payload,
        )
        for point_id, vector, payload in zip(ids, vectors, payloads)
    ]

    client.upsert(
        collection_name=settings.qdrant_collection,
        points=points,
    )

    return ids


async def search_similar(
    query_vector: List[float],
    limit: int = 5,
    score_threshold: float = 0.3,
) -> List[dict]:
    """
    Busca os chunks mais similares ao vetor de query.
    Retorna lista de resultados com payload e score.
    """
    client = get_qdrant_client()

    try:
        results = client.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="ativo",
                        match=qmodels.MatchValue(value=True),
                    )
                ]
            ),
        )

        return [
            {
                "id": str(r.id),
                "score": r.score,
                "payload": r.payload,
            }
            for r in results
        ]
    except Exception as e:
        if "Not found" in str(e) or "doesn't exist" in str(e):
            logger.warning(f"Coleção {settings.qdrant_collection} não existe ainda. Busca vazia.")
            return []
        raise e


async def delete_by_document_id(document_id: str):
    """
    Remove todos os vetores de um documento específico.
    """
    client = get_qdrant_client()

    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchValue(value=document_id),
                    )
                ]
            )
        ),
    )


async def update_document_active_status(document_id: str, ativo: bool):
    """
    Atualiza o campo 'ativo' no payload de todos os vetores de um documento.
    """
    client = get_qdrant_client()
    
    client.set_payload(
        collection_name=settings.qdrant_collection,
        payload={"ativo": ativo},
        points=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchValue(value=document_id),
                    )
                ]
            )
        ),
    )


async def get_collection_info() -> dict:
    """Retorna informações da collection."""
    try:
        client = get_qdrant_client()
        info = client.get_collection(settings.qdrant_collection)
        return {
            "status": "online",
            "points_count": info.points_count,
            "vectors_count": info.vectors_count,
        }
    except Exception as e:
        # Se for erro de not found (coleção não existe), o serviço está online, mas vazio
        if "Not found" in str(e) or "doesn't exist" in str(e):
            return {
                "status": "online",
                "points_count": 0,
                "vectors_count": 0,
                "info": "Coleção aguardando o primeiro documento"
            }
        return {"status": "error", "error": str(e)}


async def check_qdrant_health() -> bool:
    """Verifica se o Qdrant está acessível."""
    try:
        client = get_qdrant_client()
        client.get_collections()
        return True
    except Exception:
        return False
