from pathlib import Path

from config import load_config
from graph import run_once
from state import build_initial_state
from tools.preprocessing import prepare_document_corpus
from tools.retrieval import prepare_retrieval_assets


def main() -> None:
    config = load_config(Path(__file__).resolve().parent)
    documents, retrieval_handles, preprocessing_summary = prepare_document_corpus(
        config
    )
    retrieval_handles = {
        **retrieval_handles,
        **prepare_retrieval_assets(config),
    }

    state = build_initial_state(
        config,
        source_documents=documents,
        retrieval_handles=retrieval_handles,
        preprocessing_summary=preprocessing_summary,
    )

    while state.get("current_step") != "finish":
        state = run_once(state)
        if state.get("current_step") == "finish":
            break

    print("Workflow finished:", state.get("status"))
    print("Output directory:", config.paths.outputs_dir)
    print("Processed corpus:", preprocessing_summary.processed_corpus_path)
    print("FAISS index:", retrieval_handles["faiss_index_path"])


if __name__ == "__main__":
    main()
