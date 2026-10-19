import argparse

from pipeline import state as st
from pipeline.brief import run_brief
from pipeline.checks import check_brief, check_prd
from pipeline.llm import get_client
from pipeline.prd import run_prd


def report(issues: list[str]) -> None:
    if issues:
        print("Checks FAILED:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("Checks passed")


def main() -> None:
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("brief", help="stage 1: idea to brief")
    b.add_argument("idea")
    b.add_argument("--llm", choices=["ollama", "groq"], default="groq")
    p = sub.add_parser("prd", help="stage 2: approved brief to PRD")
    p.add_argument("run_id")
    p.add_argument("--llm", choices=["ollama", "groq"], default="groq")
    a = sub.add_parser("approve", help="approve a stage output")
    a.add_argument("run_id")
    a.add_argument("stage")
    s = sub.add_parser("status", help="show run state")
    s.add_argument("run_id")
    args = parser.parse_args()

    if args.cmd == "brief":
        run = run_brief(args.idea, get_client(args.llm))
        path = st.run_dir(run.run_id) / "brief.md"
        print(f"Run {run.run_id}: brief at {path}")
        report(check_brief(path.read_text()))
    elif args.cmd == "prd":
        run = run_prd(args.run_id, get_client(args.llm))
        path = st.run_dir(run.run_id) / "prd.md"
        print(f"Run {run.run_id}: PRD at {path}")
        report(check_prd(path.read_text()))
    elif args.cmd == "approve":
        run = st.approve(args.run_id, args.stage)
        print(f"Approved {args.stage} for {run.run_id}")
    else:
        print(st.load(args.run_id).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
