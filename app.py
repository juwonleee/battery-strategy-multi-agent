from pathlib import Path

from config import load_config
from graph import run_once, write_execution_log
from state import AgentState, ReportArtifact, append_execution_log, build_initial_state
from tools.preprocessing import prepare_document_corpus
from tools.retrieval import prepare_retrieval_assets


MAX_WORKFLOW_ITERATIONS = 20


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

    for _ in range(MAX_WORKFLOW_ITERATIONS):
        if state.get("current_step") == "finish":
            break
        state = run_once(state)
        if state.get("current_step") == "finish":
            break
    else:
        state = _mark_iteration_limit_exceeded(state)

    write_execution_log(state, config.log_path)
    state["report_artifacts"] = _mark_log_artifact_created(
        state.get("report_artifacts", []), config.log_path
    )

    print("Workflow finished:", state.get("status"))
    print("Output directory:", config.paths.outputs_dir)
    print("Processed corpus:", preprocessing_summary.processed_corpus_path)
    print("FAISS index:", retrieval_handles["faiss_index_path"])
    print("Execution log:", config.log_path)


def _mark_iteration_limit_exceeded(state: AgentState) -> AgentState:
    limited_state = {
        **state,
        "current_step": "finish",
        "status": "failed",
        "routing_reason": f"Stopped after reaching iteration limit ({MAX_WORKFLOW_ITERATIONS}).",
        "last_error": "Workflow iteration limit exceeded.",
    }
    limited_state["execution_log"] = append_execution_log(
        limited_state,
        step="finish",
        status="failed",
        message="Workflow stopped after reaching the maximum iteration limit.",
        attempt=limited_state.get("review_retry_count", 0),
    )
    return limited_state


def _mark_log_artifact_created(
    artifacts: list[ReportArtifact], log_path: Path
) -> list[ReportArtifact]:
    updated: list[ReportArtifact] = []
    matched = False
    for artifact in artifacts:
        if artifact.artifact_type == "log" and Path(artifact.path) == log_path:
            updated.append(
                artifact.model_copy(update={"created": log_path.exists()})
            )
            matched = True
        else:
            updated.append(artifact)
    if not matched:
        updated.append(
            ReportArtifact(
                artifact_type="log",
                path=str(log_path),
                created=log_path.exists(),
            )
        )
    return updated


if __name__ == "__main__":
    main()
