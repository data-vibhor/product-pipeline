import argparse
import json

from pipeline import state as st
from pipeline.brief import run_brief
from pipeline.build import created_files, run_build
from pipeline.checks import check_brief, check_prd
from pipeline.fix import load_issues, run_fix
from pipeline.gate import blocking_issues
from pipeline.llm import get_client
from pipeline.prd import run_prd
from pipeline.review import run_review
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
    bu = sub.add_parser("build", help="stage 3: approved PRD to code")
    bu.add_argument("run_id")
    rv = sub.add_parser("review", help="stage 4: review the generated code")
    rv.add_argument("run_id")
    rv.add_argument("--llm", choices=["ollama", "groq"], default="groq")
    iss = sub.add_parser("issues", help="list the numbered review issues")
    iss.add_argument("run_id")
    fx = sub.add_parser("fix", help="fix chosen review issues with Nemotron")
    fx.add_argument("run_id")
    fx.add_argument("numbers", help="issue numbers, for example 1,2,5-7")
    fx.add_argument("--note", default="", help="extra instruction for the fixer")
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
        run = run_revise(args.run_id, args.stage, args.feedback, get_client(args.llm))
        filename, checker, _ = STAGES[args.stage]
        path = st.run_dir(run.run_id) / filename
        print(f"Revised {args.stage}: {path} (old version kept as {args.stage}.prev.md)")
        report(checker(path.read_text()))
    elif args.cmd == "build":
        run = run_build(args.run_id)
        workspace = st.run_dir(run.run_id) / "build"
        print(f"Build status: {run.stages['build']}")
        print(f"Files created: {len(created_files(workspace))} in {workspace}")
        print(f"Log: {st.run_dir(run.run_id) / 'build.log'}")
        if run.stages["build"] == "failed":
            raise SystemExit(1)
    elif args.cmd == "review":
        run, verdict = run_review(args.run_id, get_client(args.llm))
        data = json.loads((st.run_dir(run.run_id) / "review.json").read_text())
        counts = {
            level: sum(1 for i in data["issues"] if i["severity"] == level)
            for level in ("critical", "major", "minor")
        }
        print(
            f"Verdict: {verdict} (critical {counts['critical']}, "
            f"major {counts['major']}, minor {counts['minor']})"
        )
        for issue in data["issues"][:15]:
            print(f"  [{issue['severity']}] {issue['file']}: {issue['problem']}")
        print(f"Full report: {st.run_dir(run.run_id) / 'review.md'}")
        if verdict == "block":
            raise SystemExit(1)
    elif args.cmd == "issues":
        for number, issue in enumerate(load_issues(args.run_id), start=1):
            print(f"{number}. [{issue['severity']}] {issue['file']}: {issue['problem']}")
    elif args.cmd == "fix":
        run, ok, work = run_fix(args.run_id, args.numbers, args.note)
        print(f"Fix status: {'done' if ok else 'failed'}")
        print(f"Fix workspace: {work}")
        print(f"Log: {st.run_dir(run.run_id) / 'fix.log'}")
        if ok:
            print("Review is reset. Run the review again on the fixed code.")
        else:
            print("Your current build was not changed.")
            raise SystemExit(1)
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
