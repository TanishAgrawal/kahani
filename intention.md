# Project: Script Fact/Flow Checker

An agentic system that reads a screenplay/script (scene by scene, or in chunks) and flags two categories of "oops moments" for filmmakers, screenwriters, and studio crews:

1. **Internal continuity issues** ("Flow Checker") — contradictions within the story itself.
2. **External hard-fact issues** ("Fact Checker") — real-world claims that need verification against live sources.

## Background / Builder Context
- Strong on agentic theory: the plan → act → observe → repeat loop, reflection loops, multi-agent design patterns, evals, prompt engineering.
- Zero hands-on experience: first real API integration, first GCP/`gcloud` usage, first actual agent build.
- Explicit goal: a **Vertex AI / ADK-native stack**, not a third-party agent framework wrapper (e.g. not LangChain/LangGraph as the orchestration layer).

---

## The Core Idea

### 1. Flow Checker (internal continuity — no external API)
Tracks contradictions within the story itself: a character's eye color changing, ages not adding up, a prop appearing before it's introduced, etc. Pure agentic state-tracking and reasoning over an internal "story bible" of baseline truths built up as the script is read. **Confirmed: this sub-agent should not use any external tool/MCP** — it's pure internal reasoning. Keeping this split explicit protects the "we only search where genuinely needed" design principle.

Flow Checker logic:
1. Identify the story's "flow" — baseline truths about setting and characters (soft facts) established early.
2. As more script comes in, re-analyze new content against that baseline.
3. Label each new claim: **In-flow** / **Against-flow**.
4. Maintain a memory catalogue that is added to / updated incrementally as the story progresses (input can arrive part by part, not just all at once — not necessarily the whole script dumped at once).

### 2. Fact Checker (external hard facts — needs Parallel)
Flags real-world claims (historical events, dates, laws, technology, real people/companies) that need verification against live sources.

**Honest justification for using external search here** (not just relying on the LLM's own knowledge):
- Static, well-known historical facts often don't need live search — an LLM already knows them. Decorative use of a search tool here is a weak justification.
- The genuine value is **freshness** (contemporary-set scripts referencing real companies, living public figures, current events/tech — an LLM's training cutoff is a real liability here) and **citability** (returning a source link for every flag is something an LLM alone structurally cannot do — this matters especially for legal/clearance-style claims, e.g. defamation or trademark risk in scripts depicting real entities).
- Multi-hop/compound claims (e.g. "this script implies Company X was involved in Lawsuit Y") should use a deep-research/task-style tool for chained search + reasoning, not a single search call — this is what makes the tool use genuinely agentic rather than a thin wrapper.
- **Design lean**: favor **contemporary-set scripts** and **legal/clearance-risk-flagging** as the flagship use case, not generic period-piece trivia checking — this makes the "why search" story airtight.

Fact Checker logic:
1. Identify hard facts in the text (dates, events, setting, chronology, real entities).
2. Search to verify (single search call for simple facts; multi-step/deep-research call for compound or multi-hop claims).
3. Label each: **True / False / Unknown**, with a short explanation and a source citation.
4. *(Stretch, not core scope)* Continuous monitoring: once a fact is verified, register it as "watched" — if new information surfaces later that could change the verdict, the agent alerts the user. Reframes the tool from "one-time check" to "ongoing production support." Flagged as scope risk (needs persistent state + notification loop) and hard to demo live (inherently about time passing). **Decision: build the core pipeline first; treat this as an "if time permits" add-on.**

---

## Architecture

```
Coherent (main orchestrator agent)
  → plans first: classifies user input into one of:
      - wants a report
      - asks a question (about already-processed material)
      - out of scope
  → also detects: is this an updated version of a previously-seen script?

  [Report path]
  → employs sub-agents (possibly run simultaneously):
      - Fact Checker
      - Flow Checker
    each stores its findings as context
  → Report Writer sub-agent compiles combined findings into final report

  [Question path]
  → answered from existing stored context, without re-running the full pipeline
```

**Input**: any form of plain text; can be a scene, an act, or a full script. Processing act-wise/incrementally is recommended over dumping the whole script at once.

**Memory**: a persisted catalogue/story-bible that updates incrementally; needs an explicit reset (e.g. triggered by starting a new project/script) rather than silent/implicit clearing.

---

## Tech Stack (confirmed decisions)

- **ADK (Agent Development Kit)**, Python, on **Google Cloud / Vertex AI**.
- **Model**: native Gemini models throughout (e.g. `gemini-2.5-flash` / `gemini-2.5-pro`), referenced directly by model name/`Gemini(...)` object — **no `LiteLlm` wrapper needed**, since `LiteLlm` is only required for non-Gemini models (e.g. Claude, GPT) via LiteLLM's unified interface. Native Gemini support is built into ADK.
  - Note: some Gemini 3 preview models have open issues around `thought_signature` errors on multi-step tool-call chains (relevant here since Fact Checker will do multi-step tool use). Prefer a stable Gemini 2.5 model line unless/until this is resolved.
- **External search integration**: direct **`parallel-web` Python SDK** call, wrapped as an ADK `FunctionTool`, used only by the Fact Checker sub-agent.
  - Chosen over: Grounding-with-Parallel-Search (a model-level config, harder to control response shape/citations, awkward fit for a multi-agent graph where only one sub-agent should have search access) and the Parallel MCP Server (adds a moving part / extra setup and debugging risk for a first build) and the LangChain integration (built for LangChain/LangGraph's own agent runtime — using it manually inside ADK buys nothing over the direct SDK, while adding a framework dependency).
  - Practical implication: the tool function itself should be defensive — catch API errors/timeouts inside the function and return a clean error/result string rather than letting exceptions propagate — since ADK's own agent loop provides call/retry resiliency around the tool call, but not defensive handling inside the tool function itself.
- Reasoning-layer rationale: using raw Gemini function-calling without ADK would mean hand-writing the call/parse/retry loop around every tool call for every sub-agent. ADK's agent runtime already provides that loop (call the function, handle the response, retry/re-plan on failure), which is why the whole system is being built ADK-native rather than on raw function calling.

---

## Open Design Questions (still to resolve)

1. **Is the memory catalogue shared** between Fact Checker and Flow Checker, or are they two separate stores? (Shared could let Fact Checker avoid re-searching a fact it already verified.)
2. **The "report" step right after "plan" in the flow** — is it just a label for one of the three plan branches, or an intermediate artifact, given the Report Writer produces the actual final report later?
3. **"Update version" detection** — if a script is re-uploaded/edited, should the agent diff and reprocess only the changed parts? Real feature but adds complexity (diffing).
4. **Tools list for sub-agents** beyond the Parallel search tool — likely need a memory read/write tool and a script-chunking/parsing tool; not yet finalized.
5. **Deployment target** for the running system — Cloud Run vs. Agent Engine vs. other; not yet decided.

---

## Planning Checklist (in-progress areas)

1. Scope & inputs (format, how much script per run, output format).
2. Story-bible/continuity tracking design (attributes tracked, contradiction-detection logic, where state lives).
3. External fact-checking design (which claim categories trigger search, verification confidence logic, when to escalate to a multi-step/deep-research call).
4. Agent architecture specifics (number of agents, concrete plan→act→observe→repeat loop per agent, where reflection happens, tool list per agent).
5. Tech stack mechanics (auth method, how search results feed back into agent context, hosting/deployment target).
6. Test/demo data (a script with deliberately planted continuity and fact errors).
7. Evals (a small test set of planted errors to check the agent catches them correctly).

## Progress So Far

- ✅ GCP project set up.
- ✅ First sample/starter ADK agent initiated (basic "hello world"-style agent, running locally; not yet doing anything fact/flow-checker specific).
- ✅ Parallel integration method decided: direct `parallel-web` Python SDK, wrapped as an ADK `FunctionTool`, used only by the Fact Checker sub-agent.

## Recommended Next Steps

1. Decide the deployment target (Cloud Run vs. Agent Engine).
2. Build the **Flow Checker** sub-agent first — no external API dependency, so it's the fastest path to a working end-to-end loop, and it proves out the Coherent → sub-agent → Report Writer orchestration pattern.
3. Add the **Fact Checker** + `parallel-web` SDK integration once the orchestration pattern is proven out.
4. Resolve remaining open design questions (memory catalogue sharing, report-step semantics, update-version diffing scope, full sub-agent tool lists).
