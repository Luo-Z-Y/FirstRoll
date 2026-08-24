from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PI = ROOT / ".pi"
AGENTS = PI / "agents"
PROMPTS = PI / "prompts"
EXTENSION = PI / "extensions" / "subagent"


def _agent(name: str) -> tuple[dict[str, str], str]:
    content = (AGENTS / f"{name}.md").read_text(encoding="utf-8")
    assert content.startswith("---\n")
    _, raw_frontmatter, body = content.split("---", 2)
    frontmatter = {
        key.strip(): value.strip()
        for line in raw_frontmatter.splitlines()
        if ":" in line
        for key, value in [line.split(":", 1)]
    }
    return frontmatter, body


def test_project_subagent_extension_is_complete_and_project_scoped() -> None:
    index = (EXTENSION / "index.ts").read_text(encoding="utf-8")
    discovery = (EXTENSION / "agents.ts").read_text(encoding="utf-8")

    assert 'name: "subagent"' in index
    assert "Project agent names are exactly: scout, planner, reviewer, and worker." in index
    assert 'pi.registerCommand("subagents"' in index
    assert 'default: "project"' in index
    assert 'params.agentScope ?? "project"' in index
    assert 'args.agentScope ?? "project"' in index
    assert "confirmProjectAgents" not in index
    assert '"--exclude-tools", "subagent"' in index
    assert 'args.push("--thinking", dispatchDefaults.thinkingLevel)' in index
    assert "inheritsDispatchConfig" not in index
    assert "Parallel mode rejects agents with write tools" in index
    assert "const MAX_PARALLEL_TASKS = 8" in index
    assert "const MAX_CHAIN_STEPS = 6" in index
    assert "const MAX_CONCURRENCY = 4" in index
    assert "const SUBAGENT_TIMEOUT_MS = 15 * 60 * 1000" in index
    assert "const MODEL_OUTPUT_CAP = 50 * 1024" in index
    assert "truncateOutput(`Parallel:" in index
    assert "usage: aggregateNestedUsage(results)" in index
    assert "usage: aggregateNestedUsage([result])" in index
    assert "Working directory for the agent process" not in index
    assert "fs.promises.rm(tmpDir, { recursive: true, force: true })" in index
    assert "fs.rmSync(tmpPromptDir, { recursive: true, force: true })" in index
    assert "never run mutating worker agents in parallel" in index
    assert "findNearestProjectAgentsDir" in discovery
    assert "fs.lstatSync(p).isDirectory()" in discovery
    assert 'source === "project" && !entry.isFile()' in discovery
    assert 'source: "user" | "project"' in discovery


def test_project_agents_inherit_the_parent_model_and_keep_private_data_out() -> None:
    expected_tools = {
        "scout": {"read", "grep", "find", "ls", "bash"},
        "planner": {"read", "grep", "find", "ls"},
        "reviewer": {"read", "grep", "find", "ls", "bash"},
        "worker": {"read", "grep", "find", "ls", "bash", "edit", "write"},
    }

    for name, tools in expected_tools.items():
        frontmatter, body = _agent(name)
        assert frontmatter["name"] == name
        assert "model" not in frontmatter
        assert {tool.strip() for tool in frontmatter["tools"].split(",")} == tools
        assert "AGENTS.md" in body
        assert ".firstroll" in body
        assert "credentials" in body

    _, worker = _agent("worker")
    normalised_worker = " ".join(worker.split())
    assert "Do not commit, push, deploy, switch branches" in normalised_worker
    assert "parent session owns integration and delivery" in normalised_worker


def test_subagent_workflows_and_documentation_are_discoverable() -> None:
    expected_prompts = {
        "implement.md": ("scout", "planner", "worker"),
        "scout-and-plan.md": ("scout", "planner"),
        "implement-and-review.md": ("worker", "reviewer"),
    }
    for filename, agents in expected_prompts.items():
        prompt = (PROMPTS / filename).read_text(encoding="utf-8")
        assert "subagent tool" in prompt
        assert all(f'"{agent}"' in prompt for agent in agents)

    project_docs = (PI / "README.md").read_text(encoding="utf-8")
    root_readme = (ROOT / "readme.md").read_text(encoding="utf-8")
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    agent_rules = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "/reload" in project_docs
    assert "Parallel mode rejects agents" in project_docs
    assert "retain Pi's standard symlink support" in project_docs
    assert ".pi/README.md" in root_readme
    assert "Pi subagent example" in notices
    assert "Copyright (c) 2025 Mario Zechner" in notices
    normalised_rules = " ".join(agent_rules.split())
    assert "Never run workers in parallel" in normalised_rules
    assert "must not recursively delegate" in normalised_rules
