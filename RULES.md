# Rules

## Working rules
1. The product owner decides product and strategy. Everything else is automated or done by the engineer (Claude).
2. Test on real code before handing anything over. No guessing.
3. Never paste secrets into chat. Use env vars or the host's dashboard.
4. One small step at a time; every step ends with a check that passes.
5. Bugs in a generated app are fixed by the fixer loop, driven by a failing test. Bugs in the pipeline are fixed in this repo.
6. Progress of a running fixer is judged by workspace file mtimes, not CPU.
7. Deploy kit is generated only after tests pass. Never edit a product repo's render.yaml by rsync; run `deploy-kit` first.
8. Do not delete files without approval.

## Stage contracts (run folder: runs/<id>/)

| Stage | Reads | Writes |
|---|---|---|
| brief | idea, constraints.md | brief.md, state.json |
| prd | approved brief | PRD.md |
| build | approved PRD, constraints.md | build/ (app + tests) |
| review | build/ | issues.json, verdict |
| test | build/ (Docker, network off) | test-result.json, test log |
| test-fix | failing report | fix workspace ~/pipeline-workspaces/<id>-fix, replaces build/ on success (partial edits kept) |
| deploy-kit | build/ (tests passed, /health exists) | Dockerfile.prod, start.py, .dockerignore, render.yaml, ci.yml in build/ |

## Known gaps (backlog)
- Reviewer and test-writer should be a different model family than the builder.
- PRD must state security and UI requirements, since tests only cover what the PRD says.
- Bake-off harness using the 24 mutations as the answer key.
- Change-request flow for an existing app.
