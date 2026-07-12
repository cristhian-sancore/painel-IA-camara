import os
import logging
from typing import List, Tuple
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str) -> List[Tuple[str, int]]:
    """
    Extrai texto de um PDF.
    Retorna lista de (texto, numero_pagina).
    """
    from PyPDF2 import PdfReader

    pages = []
    try:
        reader = PdfReader(file_path)
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                pages.append((text.strip(), i + 1))
    except Exception as e:
        logger.error(f"Erro ao extrair PDF {file_path}: {e}")
        raise

    return pages


def extract_text_from_docx(file_path: str) -> List[Tuple[str, int]]:
    """
    Extrai texto de um DOCX.
    Retorna lista de (texto, numero_pagina). Página = 1 para DOCX (sem paginação real).
    """
    from docx import Document

    try:
        doc = Document(file_path)
        full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        if full_text.strip():
            return [(full_text, 1)]
        return []
    except Exception as e:
        logger.error(f"Erro ao extrair DOCX {file_path}: {e}")
        raise


def extract_text_from_txt(file_path: str) -> List[Tuple[str, int]]:
    """
    Extrai texto de um TXT.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        if text.strip():
            return [(text.strip(), 1)]
        return []
    except Exception as e:
        logger.error(f"Erro ao extrair TXT {file_path}: {e}")
        raise


def extract_text(file_path: str, file_type: str) -> List[Tuple[str, int]]:
    """
    Extrai texto de um arquivo baseado no tipo.
    Retorna lista de (texto, pagina).
    """
    extractors = {
        "pdf": extract_text_from_pdf,
        "docx": extract_text_from_docx,
        "txt": extract_text_from_txt,
    }

    extractor = extractors.get(file_type.lower())
    if not extractor:
        raise ValueError(f"Tipo de arquivo não suportado: {file_type}")

    return extractor(file_path)


def chunk_text(
    pages: List[Tuple[str, int]],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[dict]:
    """
    Divide o texto em chunks com metadados.
    Retorna lista de dicts com: conteudo, pagina, chunk_index.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = []
    chunk_index = 0

    for text, page_num in pages:
        page_chunks = splitter.split_text(text)
        for chunk_text in page_chunks:
            if chunk_text.strip():
                chunks.append({
                    "conteudo": chunk_text.strip(),
                    "pagina": page_num,
                    "chunk_index": chunk_index,
                })
                chunk_index += 1

    return chunks


async def process_document(file_path: str, file_type: str) -> List[dict]:
    """
    Pipeline completo: extrai texto → chunka.
    Retorna lista de chunks prontos para embedding.
    """
    # 1. Extrair texto
    pages = extract_text(file_path, file_type)

    if not pages:
        raise ValueError("Nenhum texto encontrado no documento")

    # 2. Chunkar
    chunks = chunk_text(pages)

    if not chunks:
        raise ValueError("Nenhum chunk gerado a partir do documento")

    logger.info(f"Documento processado: {len(pages)} páginas, {len(chunks)} chunks")
    return chunks
