from pathlib import Path

from config import load_config
from graph import run_once
from state import AgentState


def main() -> None:
    config = load_config(Path(__file__).resolve().parent)

    state: AgentState = {
        "goal": "Compare LGES and CATL diversification strategies",
        "target_companies": ["LG Energy Solution", "CATL"],
        "source_documents": [str(config.manifest_path)],
        "schema_retry_count": 0,
        "review_retry_count": 0,
        "status": "initialized",
    }

    while state.get("current_step") != "finish":
        state = run_once(state)
        if state.get("current_step") == "finish":
            break

    print("Workflow finished:", state.get("status"))
    print("Output directory:", config.paths.outputs_dir)


if __name__ == "__main__":
    main()
