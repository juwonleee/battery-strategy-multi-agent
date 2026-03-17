from graph import run_once
from state import AgentState


def main() -> None:
    state: AgentState = {
        "goal": "Compare LGES and CATL diversification strategies",
        "target_companies": ["LG Energy Solution", "CATL"],
        "schema_retry_count": 0,
        "review_retry_count": 0,
        "status": "initialized",
    }

    while state.get("current_step") != "finish":
        state = run_once(state)
        if state.get("current_step") == "finish":
            break

    print("Workflow finished:", state.get("status"))


if __name__ == "__main__":
    main()
