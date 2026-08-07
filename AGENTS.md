# FirstRoll Repository Instructions

- Use British English in code comments, documentation and user-facing copy.
- Keep `readme.md` aligned with the product's current architecture, setup process,
  configuration, user workflow and material limitations whenever behaviour changes.
- Record meaningful milestones, acceptance evidence, known constraints and the next
  actionable work in `docs/PROGRESS.md` as part of the same change.
- Treat documentation maintenance as part of implementation, not as a separate optional task.
- Publish coherent, tested development checkpoints directly to `origin/master` when a feature
  or fix is complete. Do not publish every intermediate edit.
- Before publishing, inspect the complete diff, exclude local data and credentials, run
  proportionate tests and formatting checks, then create a focused commit and push `master`.
  Do not create development branches or pull requests unless the user explicitly requests one.
- Preserve the `upstream` remote and the README attribution to the original pyCinemetrics
  project. Never push FirstRoll changes to `upstream`.
- Do not commit `.firstroll`, API keys, cookies, private books, extracted book text, vectors,
  criticism caches or uploaded film clips.
