import os
import uuid
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db, async_session
from backend.models.db_models import Document, DocumentChunk
from backend.models.schemas import DocumentResponse, DocumentListResponse
from backend.middleware.auth_middleware import get_current_user, require_permission
from backend.models.db_models import User
from backend.services import document_processor, embedding_service, qdrant_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

UPLOAD_DIR = "/app/uploads"
ALLOWED_TYPES = {"pdf", "docx", "txt"}


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = 1,
    per_page: int = 20,
    search: str = "",
    user: User = Depends(require_permission("documents.view")),
    db: AsyncSession = Depends(get_db),
):
    """Lista todos os documentos indexados."""
    query = select(Document).order_by(Document.criado_em.desc())

    if search:
        query = query.where(Document.nome.ilike(f"%{search}%"))

    # Total
    count_query = select(func.count()).select_from(Document)
    if search:
        count_query = count_query.where(Document.nome.ilike(f"%{search}%"))
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginação
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    documents = result.scalars().all()

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(require_permission("documents.upload")),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload e processamento de documento.
    O processamento (parsing, chunking, embedding) roda em background.
    """
    # Validar tipo
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo '{ext}' não suportado. Use: {', '.join(ALLOWED_TYPES)}",
        )

    # Salvar arquivo
    file_id = str(uuid.uuid4())
    file_name = f"{file_id}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Criar registro no banco
    document = Document(
        id=file_id,
        nome=file.filename.rsplit(".", 1)[0],
        nome_original=file.filename,
        tipo=ext,
        tamanho_bytes=len(content),
        status="pendente",
        upload_por=user.id,
        caminho_arquivo=file_path,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Processar em background
    background_tasks.add_task(process_document_background, file_id, file_path, ext)

    return DocumentResponse.model_validate(document)


async def process_document_background(document_id: str, file_path: str, file_type: str):
    """
    Tarefa em background: processa documento, gera embeddings, indexa no Qdrant.
    """
    async with async_session() as db:
        try:
            # Atualizar status
            result = await db.execute(select(Document).where(Document.id == document_id))
            document = result.scalar_one()
            document.status = "processando"
            await db.commit()

            # 1. Processar documento → chunks
            chunks = await document_processor.process_document(file_path, file_type)

            # 2. Garantir collection no Qdrant
            dimension = await embedding_service.get_embedding_dimension()
            await qdrant_service.ensure_collection(dimension)

            # 3. Gerar embeddings e indexar por batch
            batch_size = 10
            total_chunks = 0

            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                texts = [c["conteudo"] for c in batch]

                # Gerar embeddings
                embeddings = await embedding_service.generate_embeddings_batch(texts)

                # Preparar payloads
                point_ids = []
                payloads = []
                for j, chunk in enumerate(batch):
                    point_id = str(uuid.uuid4())
                    point_ids.append(point_id)
                    payloads.append({
                        "document_id": document_id,
                        "doc_nome": document.nome,
                        "conteudo": chunk["conteudo"],
                        "pagina": chunk["pagina"],
                        "chunk_index": chunk["chunk_index"],
                        "ativo": True,
                    })

                    # Salvar chunk no PostgreSQL
                    db_chunk = DocumentChunk(
                        document_id=document_id,
                        chunk_index=chunk["chunk_index"],
                        conteudo=chunk["conteudo"],
                        pagina=chunk["pagina"],
                        qdrant_point_id=point_id,
                    )
                    db.add(db_chunk)

                # Indexar no Qdrant
                await qdrant_service.upsert_vectors(
                    vectors=embeddings,
                    payloads=payloads,
                    ids=point_ids,
                )
                total_chunks += len(batch)

            # Atualizar documento como indexado
            document.total_chunks = total_chunks
            document.status = "indexado"
            await db.commit()

            logger.info(f"Documento {document_id} indexado com {total_chunks} chunks")

        except Exception as e:
            logger.error(f"Erro ao processar documento {document_id}: {e}")
            result = await db.execute(select(Document).where(Document.id == document_id))
            document = result.scalar_one_or_none()
            if document:
                document.status = "erro"
                document.erro_msg = str(e)
                await db.commit()


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    user: User = Depends(require_permission("documents.view")),
    db: AsyncSession = Depends(get_db),
):
    """Retorna detalhes de um documento."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    user: User = Depends(require_permission("documents.delete")),
    db: AsyncSession = Depends(get_db),
):
    """Remove um documento e seus chunks do banco e do Qdrant."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    # Remover do Qdrant
    try:
        await qdrant_service.delete_by_document_id(document_id)
    except Exception as e:
        logger.error(f"Erro ao remover do Qdrant: {e}")

    # Remover arquivo físico
    if document.caminho_arquivo and os.path.exists(document.caminho_arquivo):
        os.remove(document.caminho_arquivo)

    await db.delete(document)
    await db.commit()

    return {"message": "Documento excluído com sucesso"}


@router.put("/{document_id}/toggle-active")
async def toggle_document_active(
    document_id: str,
    user: User = Depends(require_permission("documents.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Ativa ou desativa um documento para ser usado no RAG."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    document.ativo = not document.ativo
    await db.commit()

    # Atualizar vetores no Qdrant para refletir o status
    try:
        await qdrant_service.update_document_active_status(document_id, document.ativo)
    except Exception as e:
        logger.error(f"Erro ao atualizar status ativo no Qdrant: {e}")
        # Mesmo com erro, mantém o banco atualizado (o RAG usará filter se possível)

    return {"message": f"Documento {'ativado' if document.ativo else 'desativado'}", "ativo": document.ativo}


from fastapi.responses import FileResponse

@router.get("/{document_id}/file")
async def get_document_file(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retorna o arquivo físico (PDF) para visualização."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document or not document.caminho_arquivo or not os.path.exists(document.caminho_arquivo):
        raise HTTPException(status_code=404, detail="Arquivo físico não encontrado")

    media_type = "application/pdf" if document.tipo == "pdf" else "application/octet-stream"
    return FileResponse(document.caminho_arquivo, media_type=media_type, filename=document.nome_original)
