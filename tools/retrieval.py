from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from config import AppConfig, load_config
from state import EvidenceRef, ProcessedChunk, RetrievalScope

try:
    import faiss
except ImportError:  # pragma: no cover - handled at runtime when dependency is missing
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - handled at runtime when dependency is missing
    SentenceTransformer = None


class FaissRetriever:
    def __init__(
        self,
        *,
        config: AppConfig,
        index: faiss.Index,
        chunks: list[ProcessedChunk],
    ) -> None:
        self.config = config
        self.index = index
        self.chunks = chunks
        self.model = _load_embedding_model(config.embedding_model)

    def retrieve(
        self,
        query: str,
        *,
        scope: RetrievalScope,
        top_k: int | None = None,
    ) -> list[EvidenceRef]:
        normalized_query = query.strip()
        if not normalized_query:
            return []

        effective_top_k = top_k or self.config.retrieval_top_k
        if effective_top_k <= 0:
            return []

        query_vector = self.model.encode(
            [_format_embedding_text(normalized_query, is_query=True, model_name=self.config.embedding_model)],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        vectors = np.asarray(query_vector, dtype="float32")
        search_limit = min(len(self.chunks), max(effective_top_k * 12, effective_top_k))
        scores, indices = self.index.search(vectors, search_limit)

        allowed_scopes = _allowed_company_scopes(scope)
        results: list[EvidenceRef] = []
        for score, chunk_index in zip(scores[0], indices[0], strict=False):
            if chunk_index < 0:
                continue
            chunk = self.chunks[chunk_index]
            if chunk.company_scope not in allowed_scopes:
                continue

            results.append(
                EvidenceRef(
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    source_path=chunk.source_path,
                    page=chunk.page,
                    section_title=chunk.title,
                    snippet=chunk.text,
                    score=float(score),
                )
            )
            if len(results) >= effective_top_k:
                break

        return results


def prepare_retrieval_assets(config: AppConfig) -> dict[str, str]:
    _ensure_retrieval_dependencies()

    if _retrieval_assets_are_current(config):
        return {
            "faiss_index_path": str(config.faiss_index_path),
            "retrieval_metadata_path": str(config.retrieval_metadata_path),
            "retrieval_manifest_path": str(config.retrieval_manifest_path),
            "embedding_model": config.embedding_model,
        }

    chunks = load_processed_corpus(config.processed_corpus_path)
    if not chunks:
        raise ValueError(
            "Processed corpus is empty. Run preprocessing before building the retrieval index."
        )

    model = _load_embedding_model(config.embedding_model)
    passages = [
        _format_embedding_text(chunk.text, is_query=False, model_name=config.embedding_model)
        for chunk in chunks
    ]
    embeddings = model.encode(
        passages,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    vectors = np.asarray(embeddings, dtype="float32")
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    config.faiss_index_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(config.faiss_index_path))

    with config.retrieval_metadata_path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk.model_dump(mode="json"), ensure_ascii=False))
            handle.write("\n")

    config.retrieval_manifest_path.write_text(
        json.dumps(
            {
                "embedding_model": config.embedding_model,
                "processed_corpus_path": str(config.processed_corpus_path),
                "faiss_index_path": str(config.faiss_index_path),
                "retrieval_metadata_path": str(config.retrieval_metadata_path),
                "chunk_count": len(chunks),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "faiss_index_path": str(config.faiss_index_path),
        "retrieval_metadata_path": str(config.retrieval_metadata_path),
        "retrieval_manifest_path": str(config.retrieval_manifest_path),
        "embedding_model": config.embedding_model,
    }


def load_retriever(config: AppConfig) -> FaissRetriever:
    _ensure_retrieval_dependencies()

    if not config.faiss_index_path.exists() or not config.retrieval_metadata_path.exists():
        raise FileNotFoundError(
            "Retrieval assets are missing. Build them with prepare_retrieval_assets() first."
        )

    index = faiss.read_index(str(config.faiss_index_path))
    chunks = load_retrieval_metadata(config.retrieval_metadata_path)
    return FaissRetriever(config=config, index=index, chunks=chunks)


def load_processed_corpus(corpus_path: Path) -> list[ProcessedChunk]:
    if not corpus_path.exists():
        raise FileNotFoundError(
            f"Processed corpus not found: {corpus_path}. Run preprocessing first."
        )

    chunks: list[ProcessedChunk] = []
    with corpus_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = line.strip()
            if not row:
                continue
            chunks.append(ProcessedChunk.model_validate_json(row))
    return chunks


def load_retrieval_metadata(metadata_path: Path) -> list[ProcessedChunk]:
    return load_processed_corpus(metadata_path)


def _retrieval_assets_are_current(config: AppConfig) -> bool:
    required_paths = (
        config.processed_corpus_path,
        config.faiss_index_path,
        config.retrieval_metadata_path,
        config.retrieval_manifest_path,
    )
    if any(not path.exists() for path in required_paths):
        return False

    manifest = json.loads(config.retrieval_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("embedding_model") != config.embedding_model:
        return False
    if manifest.get("processed_corpus_path") != str(config.processed_corpus_path):
        return False

    corpus_mtime = config.processed_corpus_path.stat().st_mtime
    return (
        config.faiss_index_path.stat().st_mtime >= corpus_mtime
        and config.retrieval_metadata_path.stat().st_mtime >= corpus_mtime
        and config.retrieval_manifest_path.stat().st_mtime >= corpus_mtime
    )


def _ensure_retrieval_dependencies() -> None:
    if faiss is None:
        raise RuntimeError(
            "faiss-cpu is not installed. Run `pip install -r requirements.txt` first."
        )
    if SentenceTransformer is None:
        raise RuntimeError(
            "sentence-transformers is not installed. Run `pip install -r requirements.txt` first."
        )


@lru_cache(maxsize=2)
def _load_embedding_model(model_name: str) -> SentenceTransformer:
    _ensure_retrieval_dependencies()
    try:
        return SentenceTransformer(model_name, local_files_only=True)
    except Exception:
        pass

    try:
        return SentenceTransformer(model_name)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load embedding model '{model_name}'. "
            "Ensure the model is available locally or that network access is allowed."
        ) from exc


def _format_embedding_text(text: str, *, is_query: bool, model_name: str) -> str:
    stripped = text.strip()
    if "e5" in model_name.lower():
        prefix = "query: " if is_query else "passage: "
        return f"{prefix}{stripped}"
    return stripped


def _allowed_company_scopes(scope: RetrievalScope) -> set[str]:
    if scope == "market":
        return {"market", "shared"}
    if scope == "lges":
        return {"lges", "shared"}
    if scope == "catl":
        return {"catl", "shared"}
    return {"market", "lges", "catl", "shared"}


def main() -> None:
    config = load_config(
        Path(__file__).resolve().parents[1], require_openai_api_key=False
    )
    handles = prepare_retrieval_assets(config)
    retriever = load_retriever(config)
    sample_hits = retriever.retrieve(
        "battery demand growth and portfolio diversification",
        scope="cross_check",
        top_k=3,
    )
    print(f"FAISS index ready: {handles['faiss_index_path']}")
    print(f"Metadata ready: {handles['retrieval_metadata_path']}")
    print(f"Manifest ready: {handles['retrieval_manifest_path']}")
    print(f"Sample hits: {len(sample_hits)}")
    for hit in sample_hits:
        print(f"- {hit.document_id} page {hit.page} score={hit.score:.4f}")


if __name__ == "__main__":
    main()
