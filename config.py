from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(env_path: Path) -> None:
    """Load a local .env file without overwriting existing environment values."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
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
    embedding_model: str
    manifest_path: Path
    faiss_index_path: Path
    output_markdown_path: Path
    output_pdf_path: Path
    log_path: Path
    max_schema_retries: int
    max_review_retries: int
    paths: RuntimePaths


def load_config(root_dir: Path | None = None) -> AppConfig:
    base_dir = root_dir or Path(__file__).resolve().parent
    _load_dotenv(base_dir / ".env")

    paths = RuntimePaths.from_root(base_dir)
    paths.ensure_directories()

    return AppConfig(
        openai_api_key=_read_required_env("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        embedding_model=os.getenv(
            "EMBEDDING_MODEL", "intfloat/multilingual-e5-large"
        ),
        manifest_path=base_dir
        / os.getenv("DOCUMENT_MANIFEST_PATH", "data/document_manifest.json"),
        faiss_index_path=base_dir
        / os.getenv("FAISS_INDEX_PATH", "data/index/faiss.index"),
        output_markdown_path=base_dir
        / os.getenv("OUTPUT_MARKDOWN_PATH", "outputs/report.md"),
        output_pdf_path=base_dir / os.getenv("OUTPUT_PDF_PATH", "outputs/report.pdf"),
        log_path=base_dir / os.getenv("LOG_PATH", "logs/app.log"),
        max_schema_retries=_read_int_env("MAX_SCHEMA_RETRIES", 2),
        max_review_retries=_read_int_env("MAX_REVIEW_RETRIES", 2),
        paths=paths,
    )
