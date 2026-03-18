from __future__ import annotations

import json
import re
from pathlib import Path

from config import AppConfig, load_config
from state import DocumentRef, PreprocessingSummary, ProcessedChunk

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - handled at runtime when dependency is missing
    PdfReader = None


def load_document_manifest(manifest_path: Path) -> list[DocumentRef]:
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Document manifest not found: {manifest_path}. "
            "Create it from data/document_manifest.example.json."
        )

    raw_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, list):
        raise ValueError("Document manifest must be a JSON array.")

    documents = [DocumentRef.model_validate(item) for item in raw_data]
    if not documents:
        raise ValueError(
            "Document manifest is empty. Add PDF entries before running preprocessing."
        )

    seen_ids: set[str] = set()
    for document in documents:
        if document.document_id in seen_ids:
            raise ValueError(f"Duplicate document_id in manifest: {document.document_id}")
        seen_ids.add(document.document_id)

    return documents


def prepare_document_corpus(
    config: AppConfig,
) -> tuple[list[DocumentRef], dict[str, str], PreprocessingSummary]:
    if PdfReader is None:
        raise RuntimeError(
            "pypdf is not installed. Run `pip install -r requirements.txt` first."
        )

    documents = load_document_manifest(config.manifest_path)
    all_chunks: list[ProcessedChunk] = []
    chunk_files: dict[str, str] = {}

    for document in documents:
        resolved_source = _resolve_source_path(
            document.source_path,
            root_dir=config.paths.root_dir,
            manifest_dir=config.manifest_path.parent,
        )
        if not resolved_source.exists():
            raise FileNotFoundError(
                f"Source PDF not found for {document.document_id}: {resolved_source}"
            )

        document_chunks = _extract_document_chunks(
            document=document,
            resolved_source=resolved_source,
            chunk_size=config.preprocess_chunk_size,
            overlap=config.preprocess_chunk_overlap,
        )
        if not document_chunks:
            raise ValueError(
                f"No text could be extracted for {document.document_id}: {resolved_source}"
            )

        chunk_path = config.paths.processed_dir / f"{document.document_id}.chunks.json"
        chunk_path.write_text(
            json.dumps(
                [chunk.model_dump(mode="json") for chunk in document_chunks],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        chunk_files[document.document_id] = str(chunk_path)
        all_chunks.extend(document_chunks)

    config.processed_manifest_path.write_text(
        json.dumps(
            [document.model_dump(mode="json") for document in documents],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with config.processed_corpus_path.open("w", encoding="utf-8") as handle:
        for chunk in all_chunks:
            handle.write(json.dumps(chunk.model_dump(mode="json"), ensure_ascii=False))
            handle.write("\n")

    retrieval_handles = {
        "processed_manifest_path": str(config.processed_manifest_path),
        "processed_corpus_path": str(config.processed_corpus_path),
        "processed_dir": str(config.paths.processed_dir),
    }
    summary = PreprocessingSummary(
        manifest_path=str(config.manifest_path),
        processed_manifest_path=str(config.processed_manifest_path),
        processed_corpus_path=str(config.processed_corpus_path),
        document_count=len(documents),
        chunk_count=len(all_chunks),
        chunk_files=chunk_files,
    )
    return documents, retrieval_handles, summary


def _extract_document_chunks(
    *,
    document: DocumentRef,
    resolved_source: Path,
    chunk_size: int,
    overlap: int,
) -> list[ProcessedChunk]:
    reader = PdfReader(str(resolved_source))
    selected_pages = _expand_page_range(document.page_range, len(reader.pages))
    chunks: list[ProcessedChunk] = []

    for page_number in selected_pages:
        page = reader.pages[page_number - 1]
        page_text = _normalize_text(page.extract_text() or "")
        if not page_text:
            continue

        for chunk_index, chunk_text in enumerate(
            _split_text(page_text, chunk_size=chunk_size, overlap=overlap),
            start=1,
        ):
            chunks.append(
                ProcessedChunk(
                    chunk_id=f"{document.document_id}-p{page_number:03d}-c{chunk_index:02d}",
                    document_id=document.document_id,
                    title=document.title,
                    source_path=str(resolved_source),
                    source_type=document.source_type,
                    company_scope=document.company_scope,
                    published_at=document.published_at,
                    page=page_number,
                    text=chunk_text,
                    char_count=len(chunk_text),
                )
            )

    return chunks


def _resolve_source_path(source_path: str, *, root_dir: Path, manifest_dir: Path) -> Path:
    candidate = Path(source_path)
    if candidate.is_absolute():
        return candidate

    manifest_relative = (manifest_dir / candidate).resolve()
    if manifest_relative.exists():
        return manifest_relative
    return (root_dir / candidate).resolve()


def _expand_page_range(page_range: str | None, total_pages: int) -> list[int]:
    if not page_range:
        return list(range(1, total_pages + 1))

    pages: set[int] = set()
    for token in page_range.split(","):
        part = token.strip()
        if not part:
            continue
        if "-" in part:
            start_raw, end_raw = part.split("-", 1)
            start = int(start_raw)
            end = int(end_raw)
            if start > end:
                raise ValueError(f"Invalid page range: {part}")
            for page in range(start, end + 1):
                pages.add(_validate_page_number(page, total_pages))
            continue
        pages.add(_validate_page_number(int(part), total_pages))

    return sorted(pages)


def _validate_page_number(page: int, total_pages: int) -> int:
    if page < 1 or page > total_pages:
        raise ValueError(f"Page {page} is out of bounds for PDF with {total_pages} pages.")
    return page


def _normalize_text(text: str) -> str:
    cleaned = text.replace("\x00", " ")
    # Remove PDF Private Use Area characters (font symbol mis-decoding, \uf000-\uffff range)
    cleaned = re.sub(r"[\uf000-\uffff]", "", cleaned)
    # Remove PDF table cell separator artifacts encoded as /H<4-digits> (e.g. /H1118/H1118...)
    # Use exactly 4 digits to avoid greedily consuming trailing numeric values like 328,593,988
    cleaned = re.sub(r"(/H\d{4})+", " ", cleaned)
    # Replace box-drawing characters (table border lines) with a space
    cleaned = re.sub(r"[\u2500-\u257f\u2580-\u259f]", " ", cleaned)
    # Strip Windows-1252 control characters mis-decoded into the C1 range (\x80-\x9f)
    cleaned = re.sub(r"[\x80-\x9f]", "", cleaned)
    cleaned = re.sub(r"\s+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def _split_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("PREPROCESS_CHUNK_SIZE must be greater than zero.")
    if overlap >= chunk_size:
        raise ValueError("PREPROCESS_CHUNK_OVERLAP must be smaller than chunk size.")

    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    step = chunk_size - overlap

    while start < len(text):
        end = min(len(text), start + chunk_size)
        if end < len(text):
            boundary = text.rfind(" ", start + (chunk_size // 2), end)
            if boundary > start:
                end = boundary

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break
        start = max(end - overlap, start + step)

    return chunks


def main() -> None:
    config = load_config(
        Path(__file__).resolve().parents[1], require_openai_api_key=False
    )
    documents, _, summary = prepare_document_corpus(config)
    print(
        f"Prepared {summary.chunk_count} chunks from {summary.document_count} documents."
    )
    for document in documents:
        print(f"- {document.document_id}: {document.title}")


if __name__ == "__main__":
    main()
