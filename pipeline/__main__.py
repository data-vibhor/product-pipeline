import argparse

from pipeline import state as st
from pipeline.brief import run_brief
from pipeline.checks import check_brief, check_prd
from pipeline.gate import blocking_issues
from pipeline.llm import get_client
from pipeline.prd import run_prd
from pipeline.revise import STAGES, run_revise


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
    r = sub.add_parser("revise", help="apply your written feedback to a stage output")
    r.add_argument("run_id")
    r.add_argument("stage", choices=sorted(STAGES))
    r.add_argument("feedback")
    r.add_argument("--llm", choices=["ollama", "groq"], default="groq")
    a = sub.add_parser("approve", help="approve a stage output")
    a.add_argument("run_id")
    a.add_argument("stage")
    a.add_argument("--force", action="store_true", help="approve despite failed checks")
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
    elif args.cmd == "revise":
        run = run_revise(
            args.run_id, args.stage, args.feedback, get_client(args.llm)
        )
        filename, checker, _ = STAGES[args.stage]
        path = st.run_dir(run.run_id) / filename
        print(f"Revised {args.stage}: {path} (old version kept as {args.stage}.prev.md)")
        report(checker(path.read_text()))
    elif args.cmd == "approve":
        issues = blocking_issues(args.run_id, args.stage)
        if issues and not args.force:
            print("Not approved. Checks failed:")
            for issue in issues:
                print(f"  - {issue}")
            print("Rerun the stage, or approve anyway with --force")
            raise SystemExit(1)
        try:
            run = st.approve(args.run_id, args.stage)
        except ValueError as err:
            print(err)
            raise SystemExit(1) from err
        print(f"Approved {args.stage} for {run.run_id}")
    else:
        print(st.load(args.run_id).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
