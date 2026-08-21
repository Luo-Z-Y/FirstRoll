# FirstRoll Repository Instructions

- Use British English in code comments, documentation and user-facing copy.
- Keep `readme.md` aligned with the product's current architecture, setup process,
  configuration, user workflow and material limitations whenever behaviour changes.
- Record meaningful milestones, acceptance evidence, known constraints and the next
  actionable work in `docs/PROGRESS.md` as part of the same change.
- Treat documentation maintenance as part of implementation, not as a separate optional task.

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
