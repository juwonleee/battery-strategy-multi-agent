from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(env_path: Path) -> None:
    """Load a local .env file and prefer its values over inherited shell state."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            os.environ[key] = value


def _read_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got: {raw}") from exc

    if value < 0:
        raise ValueError(f"{name} must be zero or greater, got: {value}")
    return value


@dataclass(frozen=True)
class RuntimePaths:
    root_dir: Path
    data_dir: Path
    raw_dir: Path
    processed_dir: Path
    index_dir: Path
    outputs_dir: Path
    logs_dir: Path

    @classmethod
    def from_root(cls, root_dir: Path) -> "RuntimePaths":
        data_dir = root_dir / "data"
        outputs_dir = root_dir / "outputs"
        logs_dir = root_dir / "logs"
        return cls(
            root_dir=root_dir,
            data_dir=data_dir,
            raw_dir=data_dir / "raw",
            processed_dir=data_dir / "processed",
            index_dir=data_dir / "index",
            outputs_dir=outputs_dir,
            logs_dir=logs_dir,
        )

    def ensure_directories(self) -> None:
        for path in (
            self.data_dir,
            self.raw_dir,
            self.processed_dir,
            self.index_dir,
            self.outputs_dir,
            self.logs_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class AppConfig:
    openai_api_key: str
    openai_model: str
    openai_timeout_seconds: int
    openai_max_output_tokens: int
    embedding_model: str
    manifest_path: Path
    processed_manifest_path: Path
    processed_corpus_path: Path
    faiss_index_path: Path
    retrieval_metadata_path: Path
    retrieval_manifest_path: Path
    output_markdown_path: Path
    output_pdf_path: Path
    log_path: Path
    preprocess_chunk_size: int
    preprocess_chunk_overlap: int
    retrieval_top_k: int
    max_schema_retries: int
    max_review_retries: int
    paths: RuntimePaths


def load_config(
    root_dir: Path | None = None, *, require_openai_api_key: bool = True
) -> AppConfig:
    base_dir = root_dir or Path(__file__).resolve().parent
    _load_dotenv(base_dir / ".env")

    paths = RuntimePaths.from_root(base_dir)
    paths.ensure_directories()

    return AppConfig(
        openai_api_key=(
            _read_required_env("OPENAI_API_KEY")
            if require_openai_api_key
            else os.getenv("OPENAI_API_KEY", "").strip()
        ),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        openai_timeout_seconds=_read_int_env("OPENAI_TIMEOUT_SECONDS", 60),
        openai_max_output_tokens=_read_int_env("OPENAI_MAX_OUTPUT_TOKENS", 2000),
        embedding_model=os.getenv(
            "EMBEDDING_MODEL", "intfloat/multilingual-e5-large"
        ),
        manifest_path=base_dir
        / os.getenv("DOCUMENT_MANIFEST_PATH", "data/document_manifest.json"),
        processed_manifest_path=base_dir
        / os.getenv(
            "PROCESSED_MANIFEST_PATH", "data/processed/document_manifest.processed.json"
        ),
        processed_corpus_path=base_dir
        / os.getenv("PROCESSED_CORPUS_PATH", "data/processed/corpus.jsonl"),
        faiss_index_path=base_dir
        / os.getenv("FAISS_INDEX_PATH", "data/index/faiss.index"),
        retrieval_metadata_path=base_dir
        / os.getenv("RETRIEVAL_METADATA_PATH", "data/index/faiss_metadata.jsonl"),
        retrieval_manifest_path=base_dir
        / os.getenv("RETRIEVAL_MANIFEST_PATH", "data/index/retrieval_manifest.json"),
        output_markdown_path=base_dir
        / os.getenv("OUTPUT_MARKDOWN_PATH", "outputs/report.md"),
        output_pdf_path=base_dir / os.getenv("OUTPUT_PDF_PATH", "outputs/report.pdf"),
        log_path=base_dir / os.getenv("LOG_PATH", "logs/app.log"),
        preprocess_chunk_size=_read_int_env("PREPROCESS_CHUNK_SIZE", 1200),
        preprocess_chunk_overlap=_read_int_env("PREPROCESS_CHUNK_OVERLAP", 200),
        retrieval_top_k=_read_int_env("RETRIEVAL_TOP_K", 6),
        max_schema_retries=_read_int_env("MAX_SCHEMA_RETRIES", 2),
        max_review_retries=_read_int_env("MAX_REVIEW_RETRIES", 2),
        paths=paths,
    )
