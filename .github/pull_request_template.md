## Summary

- What changed and why?

## Risk and trust boundaries

- Which runtime, data, credential or deployment boundary changes?
- What is the rollback or safe fallback?

## Validation

- List the local checks and acceptance evidence.

## Delivery checklist

- [ ] The complete diff against `origin/master` has been reviewed.
- [ ] No local data, credentials, private source text, vectors, caches or uploaded clips are included.
- [ ] Proportionate tests, formatting checks and builds pass.
- [ ] `readme.md` and `docs/PROGRESS.md` are updated when behaviour changes.
- [ ] The branch is current with `origin/master` and every required CI check passes.
- [ ] Any production effect and rollback path are understood.

Merging this pull request does **not** approve production. The sealed deployment must wait for a
separate human approval in the protected GitHub `production` environment.
