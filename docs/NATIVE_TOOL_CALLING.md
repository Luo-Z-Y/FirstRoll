# Native Tool Calling in the Local Research Agent

**Status:** implemented locally, default-off and synthetically tested; real-provider validation remains blocked by A01R approval

This note compares the former JSON-in-assistant-content planner protocol with the current native
`tool_calls` protocol. It also records the safety boundary that deliberately remains outside the
model. This applies only to the local autonomous research planner. The fixed production Deep Study
workflow does not expose tools to its model, and no Agent HTTP route exists.

## Executive summary

The planner used to receive tool descriptions as ordinary prompt data and return this text:

```json
{"target_gap":"evidence_class_diversity","tool":"fetch_crossref_research"}
```

It now receives one native function definition per currently addressable research capability and must
return exactly one native function call:

```json
{
  "id": "call_123",
  "type": "function",
  "function": {
    "name": "fetch_crossref_research",
    "arguments": "{\"target_gap\":\"evidence_class_diversity\"}"
  }
}
```

This is a protocol change, not an authority change. DeepSeek proposes one function and one measured
gap. FirstRoll still validates the envelope, function, arguments, gap, capability relationship,
provider state, graph state and budgets before trusted Python constructs the provider arguments and
executes anything.

## Code path

```text
research_graph.nodes.policy
  → deterministic decide_next_action()
  → research_graph.nodes.choose_tool
  → LocalResearchGraphServices.choose_tool
  → DeepSeekStudyService.plan_research_tool
      → native tools request
      → exactly one tool_calls response
      → strict argument parsing
      → tool/gap validation
  → research_graph.nodes.authorise_tool
  → authorise_tool_request
  → research_graph.nodes.execute_tool
  → LocalResearchGraphServices.run_tool
  → LocalAttributedSourceAcquirer.acquire
  → hard-coded Guardian/Crossref/Douban/Letterboxd/video adapter
  → typed EvidencePacket rebuild
  → deterministic evidence reassessment
```

The principal implementation files are:

- `app/backend/study_service.py` — native request schemas and response validation;
- `app/backend/local_research_agent.py` — deterministic/model planner selection and adapter dispatch;
- `app/backend/research_agent_contract.py` — allow-list, budgets and independent authorisation;
- `app/backend/research_graph/nodes.py` — propose, authorise and execute separation;
- `tools/evaluate_agent_acquisition.py` — A01R protocol-integrity acceptance target;
- `tests/test_local_research_agent.py` — payload, privacy and malformed-call coverage.

## Before: JSON embedded in assistant content

The previous planner request used an ordinary structured-output response:

```python
payload = {
    "model": self.model,
    "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ],
    "thinking": {"type": "disabled"},
    "response_format": {"type": "json_object"},
    "temperature": 0,
    "max_tokens": 128,
}
```

Tool names, descriptions, addressable gaps and provider states were serialised inside the user
message. The response was read from normal assistant content:

```python
content = response["choices"][0]["message"]["content"]
proposal = self._parse_json(content)
selected = ToolName(str(proposal.get("tool") or ""))
target_gap = EvidenceGap(str(proposal.get("target_gap") or ""))
```

The application still authorised the result, but the provider did not distinguish a tool proposal
from ordinary generated text. A model could also return explanatory prose around malformed JSON,
which FirstRoll then had to reject as a content-format failure.

## After: native `tool_calls`

### Request

The new request puts capabilities in the API's dedicated `tools` field:

```python
payload = {
    "model": self.model,
    "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": safe_context},
    ],
    "tools": native_tools,
    "tool_choice": "required",
    "thinking": {"type": "disabled"},
    "temperature": 0,
    "max_tokens": 128,
}
```

`response_format: json_object` is no longer present. Every currently addressable tool receives a
function definition of this form:

```json
{
  "type": "function",
  "function": {
    "name": "fetch_crossref_research",
    "description": "Propose one bounded research action for matched scholarly publication abstracts. FirstRoll independently authorises and constructs every execution argument.",
    "parameters": {
      "type": "object",
      "properties": {
        "target_gap": {
          "type": "string",
          "enum": ["evidence_class_diversity", "focus_relevance"]
        }
      },
      "required": ["target_gap"],
      "additionalProperties": false
    }
  }
}
```

The `target_gap` enum is narrowed separately for each planning turn and function. For example,
Guardian is not offered for an evidence-class-diversity-only gap, while Crossref and video text are.
A provider explicitly known as `credentials_required`, `not_installed` or `unavailable` is omitted
before transport. If no ready capability can address the measured gaps, FirstRoll stops before a
model call.

### Response

FirstRoll now reads only the native channel:

```python
message = response["choices"][0]["message"]
tool_calls = message["tool_calls"]
```

The response must contain exactly one item with:

- a non-empty call ID;
- `type == "function"`;
- a function object;
- a recognised function name;
- arguments encoded as a JSON string.

Arguments are parsed through a Pydantic model with `extra="forbid"`:

```python
class NativeResearchToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_gap: EvidenceGap
```

Consequently, this is accepted:

```json
{"target_gap":"independent_origins"}
```

This is rejected before authorisation:

```json
{
  "target_gap": "independent_origins",
  "film_id": "model-invented-id",
  "url": "https://model-selected.example",
  "limit": 999
}
```

There is deliberately no fallback to the legacy JSON content protocol. Assistant content without one
native call, zero calls, multiple calls, a missing call ID, non-function calls, dictionary-valued
arguments, malformed JSON and additional arguments all fail closed.

## What the model controls

The model controls only two values:

1. one function name from the capabilities supplied on that exact turn;
2. one `target_gap` value from that function's turn-specific enum.

It does not control:

- film identity;
- provider IDs;
- URLs;
- search limits;
- credentials or cookies;
- HTTP headers;
- filesystem paths;
- whether the action is authorised;
- whether another planning turn occurs;
- synthesis, repair or retry budgets.

## What FirstRoll still controls

Native schema acceptance is not treated as authorisation. After parsing, the existing deterministic
layers remain:

1. `plan_research_tool()` checks that the function was offered, the gap was measured and the
   capability can address it.
2. `choose_tool()` checks that the returned value is a `ToolName` and remains in the graph's
   turn-specific allow-list.
3. `authorise_tool_request()` checks terminal state, current policy action, attempted providers and
   external-call limits.
4. `execute_tool()` refuses to run without the explicit authorisation flag.
5. `LocalAttributedSourceAcquirer.acquire()` constructs all arguments from the verified film record
   and dispatches through a hard-coded adapter map.
6. Retrieved evidence is normalised into typed records and cannot authorise a later action.

A native function call is therefore an untrusted proposal. It is never an executable Python callable
supplied by the model.

## Old and new control comparison

| Concern | Former content-JSON planner | Native-tool planner | Preserved application control |
|---|---|---|---|
| Capability declaration | Tool records inside user JSON | Dedicated `tools` definitions | Only current allow-list is exposed |
| Selection response | JSON in `message.content` | One item in `message.tool_calls` | Enum and policy validation |
| Tool requirement | Prompt instruction | `tool_choice: required` plus validation | Zero/multiple calls fail |
| Parallel proposals | Not representable in expected schema | Provider may return several | FirstRoll rejects anything except one |
| Arguments | `tool` and `target_gap` content fields | Function name and `target_gap` argument | Extra arguments forbidden |
| Provider execution arguments | Constructed by FirstRoll | Constructed by FirstRoll | Model cannot supply IDs, URLs or limits |
| Result returned to planner | No raw result | No raw `role: tool` result | Typed packet and safe aggregates only |
| Continuation | LangGraph policy | LangGraph policy | Model cannot self-loop |
| Authorisation | Separate deterministic node | Same separate node | No change |
| Failure accounting | Graph/report counters | Same counters plus protocol label | No hidden retry |

## Why no `role: tool` continuation is sent

Native APIs commonly append the assistant's call and raw function result to a conversation, then let
the model decide what to do next. FirstRoll deliberately does not do that. Provider pages, reviews,
abstracts and captions are untrusted and may contain instructions. The adapter first converts output
to typed evidence, rebuilds the packet and runs deterministic gap assessment. If another turn is
justified, a fresh planner call receives safe counts and gap names rather than raw provider text.

This retains the native request/response protocol without changing the prompt-injection boundary or
giving the model ownership of the loop.

## Research capabilities

| Native function name | Trusted implementation | Model-supplied argument |
|---|---|---|
| `fetch_guardian_reviews` | Guardian public-web adapter | `target_gap` only |
| `fetch_crossref_research` | Crossref abstract adapter | `target_gap` only |
| `fetch_letterboxd_reviews` | Configured API or public-web adapter | `target_gap` only |
| `fetch_douban_reviews` | Python-controlled Douban MCP client | `target_gap` only |
| `search_youtube_resources` | YouTube/Bilibili search and text extraction | `target_gap` only |

One Agent-level function can contain more than one low-level operation. Douban normally performs MCP
`search-movie` and `list-movie-reviews` calls. Video research can query two platforms and enrich
several records. `external_tool_calls` therefore remains a logical graph-action metric, while A01R's
physical observation pool and timings account separately for provider acquisition.

## Unchanged non-tool model calls

Study generation, structural repair, claim audit, targeted editing and coaching continue to use
ordinary JSON structured output. They are invoked by deterministic graph/controller stages and have
no research tools. Native tool calling applies only to acquisition planning.

## Telemetry and A01R acceptance

Model planning decisions now carry:

```json
{
  "strategy": "model_gap_planner",
  "protocol": "native_tool_calls",
  "tool": "fetch_crossref_research",
  "target_gap": "evidence_class_diversity"
}
```

Deterministic decisions carry `protocol: deterministic_router`. A01R adds a
`planner_protocol_integrity` target requiring every model planning turn to use native tool calls and
every baseline turn to remain deterministic. The historical A01 report is unchanged and is explicitly
labelled as having used `legacy_json_in_assistant_content`.

## Synthetic acceptance coverage

Tests verify that:

- the request uses `tools` and `tool_choice: required`;
- `response_format` is absent from planner calls;
- only addressable functions and gap enums are exposed;
- private evidence, private provider labels, secrets and unknown issue codes do not enter the request;
- known unavailable tools stop before model transport;
- legacy content JSON is rejected;
- zero and parallel native calls are rejected;
- a missing call ID is rejected;
- non-JSON argument objects are rejected;
- model-supplied film IDs, limits or other execution arguments are rejected;
- out-of-policy tools and gaps are rejected;
- A01R fails its protocol target if a model turn reports the legacy protocol.

Run the focused checks with:

```bash
uv run python -m pytest -q \
  tests/test_local_research_agent.py \
  tests/test_research_graph.py \
  tests/test_research_agent_contract.py \
  tests/test_agent_acquisition_evaluator.py \
  tests/test_autonomous_agent_programme.py
```

## Current limitation

No paid DeepSeek request was made for this migration. Synthetic transports establish payload and
validation behaviour, not provider compatibility or planner quality. A01R remains the required
provider-backed test, under a fresh exact budget and one-run lock. Until that passes and receives the
owner's blinded packet review, native tool calling does not establish acquisition value and is not
authorised for production.
