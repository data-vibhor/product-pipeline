import argparse
import json
import sys
import tempfile
from pathlib import Path

from bakeoff.harness import run_candidate, score_suite


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bakeoff")
    sub = parser.add_subparsers(dest="cmd", required=True)
    score = sub.add_parser("score", help="score the tests already in an app folder")
    score.add_argument("app_dir", type=Path)
    score.add_argument("--python", required=True, help="python of a venv with the app deps")
    run = sub.add_parser("run", help="have a model write tests, then score them")
    run.add_argument("model", help="for example opencode/glm-5.3-flash-free")
    run.add_argument("app_dir", type=Path, help="app folder that has a PRD.md")
    run.add_argument("--python", required=True)
    run.add_argument("--out", type=Path, default=Path("bakeoff-results"))
    args = parser.parse_args(argv)
    if args.cmd == "score":
        with tempfile.TemporaryDirectory() as tmp:
            result = score_suite(args.app_dir, args.python, Path(tmp))
        for name, status in result.results:
            print(f"{status:9} {name}")
        print(result.summary())
        return 0 if result.clean_passed else 1
    outcome = run_candidate(args.model, args.app_dir, args.python, args.out)
    print(json.dumps({k: v for k, v in outcome.items() if k != "results"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
