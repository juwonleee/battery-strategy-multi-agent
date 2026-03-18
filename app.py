from pathlib import Path

from config import load_config
from graph import run_once
from state import build_initial_state


def main() -> None:
    config = load_config(Path(__file__).resolve().parent)

    state = build_initial_state(config)

    while state.get("current_step") != "finish":
        state = run_once(state)
        if state.get("current_step") == "finish":
            break

    print("Workflow finished:", state.get("status"))
    print("Output directory:", config.paths.outputs_dir)


if __name__ == "__main__":
    main()
