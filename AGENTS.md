# FirstRoll Repository Instructions

- Use British English in code comments, documentation and user-facing copy.
- Keep `readme.md` aligned with the product's current architecture, setup process,
  configuration, user workflow and material limitations whenever behaviour changes.
- Record meaningful milestones, acceptance evidence, known constraints and the next
  actionable work in `docs/PROGRESS.md` as part of the same change.
- Treat documentation maintenance as part of implementation, not as a separate optional task.

## Architecture documentation gate

- Treat a change as architectural when it alters a service or component boundary, deployment
  topology, authentication or trust boundary, persistent or transient state, provider/evidence
  flow, material request sequence, Agent lifecycle/tool budget/terminal state, or CI/CD approval and
  rollback path.
- In the same branch as an architectural change, update every affected typed Archify source under
  `docs/architecture/`, regenerate its paired self-contained HTML, and reconcile
  `docs/ARCHITECTURE.md`, `docs/ARCHITECTURE_ATLAS.md`, `readme.md` and `docs/PROGRESS.md`.
- Edit the typed JSON source, never the generated HTML. Run Archify `validate` with the `showcase`
  quality profile after each source edit, then use `deliver` for the final HTML and run
  `visual-check` before handoff. Commit the JSON and HTML together.
- Keep diagram claims pinned to a real source revision and distinguish production, private-local,
  experimental and planned behaviour. Report deterministic validation, browser evidence and
  perceptual review separately; never conceal a failed or unavailable check.
- An internal refactor that preserves every documented contract need not regenerate a diagram, but
  the final handoff must state that the architecture was reviewed and why no Archify source changed.

## Pi subagent workflow

- Trusted Pi sessions may use the project-local `subagent` tool for isolated reconnaissance,
  planning, review or one bounded implementation task.
- Parallel delegation is for independent read-only scout, planner or reviewer work only. Never run
  workers in parallel or edit overlapping files in the parent while a worker is active.
- Delegated agents must not inspect `.firstroll` or other private material and must not recursively
  delegate, commit, push, deploy, switch branches or otherwise alter Git integration state.
- Treat every subagent result as advisory. The parent session owns complete-diff inspection, tests,
  documentation reconciliation, commits, pull requests and delivery.

## Protected delivery workflow

- Treat `master` as the production source and as read-only during development. Never commit or push
  directly to `master`, force-push it, bypass its rules or disable its protection.
- Start every feature, fix, documentation or infrastructure change from the current
  `origin/master` on a short-lived branch named `feat/...`, `fix/...`, `docs/...` or `chore/...`.
  Do not create a permanent `local`, `develop` or other shadow production branch.
- Local commits and local previews are safe development checkpoints. Push the short-lived branch to
  `origin` when remote CI or backup is useful; branch pushes and pull requests must not receive a
  production deployment credential or deploy to the live site.
- Before publishing a branch, inspect its complete diff against `origin/master`, exclude local data
  and credentials, and run proportionate tests, formatting checks and builds.
- Publish each coherent checkpoint by opening a pull request into protected `master`. Keep it current
  with `origin/master`, wait for every required check to pass and resolve review conversations before
  merging. Do not merge a failing, pending or stale pull request.
- Delete the short-lived remote branch after merge. Agents may merge a green pull request unless the
  user asks to review it first; merging is not production approval.
- Every successful `master` merge may build a sealed production artefact, but deployment must stop at
  the protected GitHub `production` environment until a human repository owner approves that exact
  run. Agents must report the pending deployment and must not approve it, bypass it or weaken the
  gate unless the user explicitly instructs them to approve that specific deployment.

- Preserve the `upstream` remote and the README attribution to the original pyCinemetrics project.
  Never push FirstRoll changes to `upstream`.
- Do not commit `.firstroll`, API keys, cookies, private books, extracted book text, vectors,
  criticism caches or uploaded film clips.
