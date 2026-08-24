# FirstRoll Pi subagents

This trusted project configuration adds a `subagent` tool to Pi. Each delegated task runs in a
separate, non-persistent Pi process with an isolated context window. The child inherits the parent
session's active model and thinking level, but not its conversation.

Pi loads `.pi/extensions/subagent/index.ts` automatically after the repository is trusted. Restart Pi
or run `/reload` after pulling these files into an existing session. Use `/subagents` to list the
available roles.

## Roles

| Agent | Access | Intended use |
|---|---|---|
| `scout` | Read-only tools | Focused repository reconnaissance and compressed hand-off context |
| `planner` | Read-only tools | Concrete implementation plans without edits |
| `reviewer` | Read-only tools and explicitly read-only Bash | Quality, security and maintainability review |
| `worker` | Built-in read/write tools | One bounded implementation task; the parent owns Git and delivery |

All roles inherit the repository's `AGENTS.md`. Their prompts explicitly exclude `.firstroll`,
credentials, private books, extracted text, vectors, cookies and uploaded film clips. The worker is
also instructed not to commit, push, deploy or alter branches. These are prompt-level controls, not
an operating-system sandbox: the parent session must inspect every resulting diff.

## Usage

Ask Pi naturally, for example:

```text
Use a scout subagent to map the authentication flow.
Run two read-only scouts in parallel: one for API routes and one for browser state.
Use the reviewer subagent to inspect the current diff.
Use one worker subagent to add the agreed tests, then inspect its changes yourself.
```

The tool supports three shapes:

- single: one `agent` and one `task`;
- parallel: up to eight tasks, with at most four child processes running at once;
- chain: up to six sequential tasks, with `{previous}` inserting the preceding result.

Reusable prompt templates are available as `/implement`, `/scout-and-plan` and
`/implement-and-review`. Project agents are the default scope and Pi asks for confirmation before
running them in interactive mode. Project agent directories and files may not be symlinks. Set
`agentScope` to `both` only when user-level agents should also be considered; user-level definitions
remain under the developer's control and retain Pi's standard symlink support.

## Boundaries

- Parallel mode rejects agents with `edit`, `write` or unrestricted default tool access. Do not let
  the parent edit overlapping files while a single worker is active.
- Each child consumes provider quota independently; parallel delegation multiplies token use.
- Each child is stopped after fifteen minutes and child sessions use `--no-session`, so only the
  parent tool result is retained.
- Model-visible output is capped at 50 KB; full task details remain in the parent session's tool data.
- Delegated working directories cannot be overridden; every child starts from the parent repository
  directory.
- The extension is adapted from Pi's MIT-licensed subagent example and is tested with
  `@earendil-works/pi-coding-agent` 0.84.2.
