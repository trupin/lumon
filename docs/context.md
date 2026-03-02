# Agent Language

Name: **Lumon**

## One-liner

A minimal, safe, pseudocode-like interpreted language that defines the cognitive boundary of an AI agent.

## Core Concept

The language is the agent's entire reality. An agent can only think and act in terms of the language's primitives. If a primitive doesn't exist, the agent cannot conceive of the action — not because it's blocked, but because the concept doesn't exist in its world.

This is fundamentally different from sandboxing. Sandboxing assumes the agent knows about dangerous things and prevents access — an arms race. This language removes the awareness entirely. There is nothing to escape from.

## Principles

1. **Safety by construction** — elementary built-ins are safe. Composition of safe primitives produces safe programs. No runtime enforcement needed.
2. **Self-implementing agents** — agents write their own capabilities at runtime using only the language's primitives. They build their toolbox as they go.
3. **Code is memory** — agent-authored functions persist as code. Because the language is compact pseudocode, reloading capabilities is cheap in tokens. The code is the agent's memory, not context.
4. **Discoverable by design** — a hierarchical interface defines what capabilities can exist. Agents browse the interface (cheap) before loading implementations (expensive). Descriptions are part of the language, not comments.
5. **Bounded extensibility** — users can add new primitives, consciously expanding the agent's reality. Each extension is an auditable decision.
6. **Environment-agnostic** — the interpreter runs anywhere (local, cloud, hosted). The language is the same regardless.

## Architecture

### Two layers

**Interface (community-maintained)**
- Hierarchy of namespaces, function signatures, and semantic descriptions
- Defines "what can exist" — the shape of all possible capabilities
- Carefully reviewed, versioned, stable
- Acts as a standard library spec and a curriculum for agents

**Implementation (agent-authored)**
- The actual code behind each interface function
- Written by the agent at runtime, using only the language's primitives
- Varies per user — same interface, different implementations depending on environment
- New users start with a full interface and zero implementations

### Trust model

1. Trust the language primitives — small, auditable, community-reviewed
2. Trust composition — if A is safe and B is safe, A+B is safe (a property of the language design)
3. Never trust the agent's intent — doesn't matter, because intent can only be expressed through safe primitives

### Discovery model

The interface is a token-efficient capability manifest:
- Agent reads the namespace tree first (lightweight)
- Finds relevant functions by description (semantic, not just by name)
- Loads implementation only when calling or extending
- Checks if a local implementation exists before writing a new one

## Why not an existing language?

- Python/JS are too expressive — impossible to guarantee safety by construction
- A new language can make constraints structural, not bolted on
- Pseudocode-like syntax means the language spec fits in a single prompt — no training data needed
- Compact syntax means agent-authored code is cheap to persist and reload
- Descriptions as first-class language constructs (not comments) enable semantic discovery

## Comparison to current models

| | MCP / Tool Use | Agent Language |
| :---- | :---- | :---- |
| Capabilities | Pre-defined by developers | Self-authored by agent at runtime |
| Adding new ones | Human writes code, registers tool | Agent writes code in safe language |
| Context cost | Every tool schema in context | Only language spec + interface manifest |
| Safety | Trust each tool implementation | Trust the language's primitives |
| Auditability | Check each tool call | Read the agent's source code |
| Persistence | Stateless per session | Code is memory, persists across sessions |
| Discovery | Flat list of tools | Hierarchical, semantic, incremental |

## Function I/O Design

### Type system

**Typed signatures, untyped internals.** The interface layer (define) has full types on every parameter and return value. Function bodies (implement) don't declare types for locals — the type checker infers them.

Primitive types: `text`, `number`, `bool`, `none`, `tag` (`:ok`, `:error(text)`).
Parameterized: `list<text>`, `map<number>`. Lists are homogeneous.
Structural maps: `{name: text, age: number}` — known fields with known types.
Type unions: `:ok(text) | :error(text)`, `number | none`.
Function types: `fn(a) -> b` — for higher-order functions.

The type checker runs before execution and catches **all** type errors statically. No type errors occur at runtime.

### Signatures

- Named parameters with types and descriptions
- Default values via `= value`
- Single return value (use `map` for multiple)
- Descriptions are first-class on parameters and return values

### Error handling

Two error layers. **Recoverable errors** are tag returns (`:ok | :error(text)`) — the Lumon program handles them via `match`, execution continues. **Interpreter errors** (undefined variable, type mismatch) halt execution and emit structured JSON for the agent to self-heal. No try/catch mechanism.

### Example

```
define file.read
  "Read the contents of a file"
  takes:
    path: text "The file to read"
    encoding: text "Character encoding" = "utf-8"
  returns: text "The file contents"

implement file.read
  let raw = io.read_bytes(path)
  let result = text.decode(raw, encoding)
  return result
```

The `define` block is the contract — typed, described, browsable. The `implement` block is the agent's code — compact, no type annotations on locals. The interpreter type-checks at the boundary (do arguments match the signature?) without needing full type inference internally.

## Memory Model

Declarative, OCaml-inspired. Core properties:

### Immutability by default

Variables are bindings, not mutable boxes. Once `x = 5`, x is 5 forever. No reassignment — you create new bindings. This eliminates shared mutable state bugs and makes agent code trivially auditable (no hidden state changes).

### Shadowing

Reusing a name creates a new binding, doesn't mutate the old one. This is the OCaml way — simpler to implement than enforcing unique names, and still safe.

```
let x = 10
let x = x + 1   -- shadows, does not mutate. Old x is gone.
```

### Expression-oriented

Everything returns a value. `match`, `if`, function calls — all expressions. No statement/expression distinction.

### Pattern matching

Destructure data directly instead of if/else chains:

```
match result
  {status: "ok", data: d} -> process(d)
  {status: "error", msg: m} -> log(m)
  none -> fallback()
```

### No loops — functional iteration

No `for`/`while`. Use `list.map`, `list.filter`, `list.fold` instead. Avoids infinite loop footguns, more declarative, and safe (no index-out-of-bounds).

```
let points = list.flat_map(items, fn(item) -> text.extract_key_points(item))
let unique = list.deduplicate(points)
let ranked = list.sort_by(unique, fn(p) -> text.relevance_score(p))
let top = list.take(ranked, max_points)
```

### Lambdas

`fn(args) -> expr` for single-expression lambdas, or multi-line with indentation where the last expression is the implicit return value. `implement` blocks still require explicit `return`.

```
-- Single-expression
fn(x) -> x * 2

-- Multi-line (last expression is the return value)
fn(tag) ->
  let matching = items |> list.filter(fn(item) -> text.contains(item, tag))
  {key: tag, value: matching}
```

### Map literals

`{key: value}` syntax for inline maps:

```
return {status: "ok", data: text.decode(bytes, encoding)}
```

### Why this model

- Immutability = easy to audit, no hidden side effects
- Pattern matching = compact (good for token cost)
- Functional iteration = no infinite loops, no off-by-one errors
- Expression-oriented = less syntax, everything composes
- Tradeoff: LLMs are trained mostly on imperative code, but since the spec fits in one prompt, the LLM learns the style from the spec itself

## POC: Self-Implementing Obsidian Agent

### The pitch

A personal assistant agent that manages an Obsidian vault and reads the open web — with zero permission prompts. It starts knowing nothing except the language spec. As you talk to it, it implements its own tools, saves them as code, and reuses them across sessions. Over time it becomes deeply capable, but its context cost stays flat.

### Why this proves the concept

**Safety without gates.** The agent reads arbitrary web content — including adversarial pages with prompt injection. It cannot act on injected instructions because the concepts (execute code, send data, call APIs) don't exist in its language. The worst it can do is write odd notes to your vault. A blacklist of unlawful domains is maintained as config checked by the `http.get` primitive — the agent doesn't even know the blacklist exists.

**Self-implementing, not pre-built.** Day 1, you say "check my inbox." The agent has no `inbox` namespace implemented. It reads the interface, finds `inbox.read` and `inbox.summarize`, writes implementations using `io.read` and `text.*` primitives, and saves them. Those functions now exist as code on disk.

**Complexity grows, context doesn't.** Day 100, the agent has hundreds of self-authored functions — `inbox.triage`, `health.check_plan`, `grocery.add`, `news.fetch_headlines`, `web.extract_article`. But its context only holds the language spec + the interface manifest. Capabilities are loaded from disk only when called. Traditional agents get slower and more expensive as they gain tools (more schemas in context). This one stays cheap.

**Each agent is unique.** Two users start with the same interface. One asks about health and groceries — their agent builds `health.*` and `grocery.*`. The other tracks projects and news — their agent builds `project.*` and `news.*`. Same language, same interface, completely different machines shaped by usage.

### The demo arc

```
Session 1: "Summarize my inbox"
  → Agent writes inbox.read, inbox.summarize
  → Saves implementations to disk

Session 5: "Check the news for AI agent developments"
  → Agent writes web.search, web.extract_article, news.filter_topic
  → Composes them into a workflow
  → Results written to vault

Session 20: "Check my inbox, cross-reference with my diet plan,
             add health items to grocery list"
  → Agent composes inbox.read + health.check_plan + grocery.add
  → All previously self-authored, zero re-implementation
  → Context cost: same as session 1
```

### POC built-ins (minimal safe set)

| Namespace | Primitives | Safety note |
| :---- | :---- | :---- |
| `io` | `read`, `write`, `list_dir` | Bounded to root directory (cwd) |
| `http` | `get` | Read-only, blacklist-filtered, no POST/auth |
| `text` | `split`, `join`, `contains`, `replace`, `slice`, `length` | Pure functions |
| `list` | `map`, `filter`, `fold`, `flat_map`, `sort_by`, `take`, `deduplicate`, `length` | Pure functions |
| `map` | `get`, `set`, `keys`, `values`, `merge` | Pure (returns new map) |
| `number` | `add`, `subtract`, `multiply`, `divide`, `round`, `compare` | Pure functions |
| `bool` | `and`, `or`, `not` | Pure functions |

Everything else — `inbox.*`, `task.*`, `health.*`, `news.*`, `web.*`, `grocery.*` — is authored by the agent at runtime.

### Invisible boundaries

Primitives have built-in restrictions that the agent cannot see or introspect. Restricted operations return `:error` indistinguishable from normal failures. The agent works with what it gets.

**Filesystem (`io.*`):** All paths are relative to the **root directory** — the working directory where the interpreter is launched. The interpreter normalizes paths and resolves symlinks before checking. Paths that resolve outside the root return `:error` (indistinguishable from "file not found"). The agent can read and write anywhere within the root.

**HTTP (`http.get`):** Filtered by two blacklist layers:

1. **Built-in blacklist** — shipped with the interpreter, maintained by the project maintainers. Covers illegal content, malware domains, etc. Users cannot disable it.
2. **User blacklist** — a local config file the user maintains. Personal boundaries (e.g. no social media, no specific sites).

The interpreter checks both before any request. Blocked URLs return `:error` — indistinguishable from "unreachable." The agent has no visibility into the blacklist's existence, contents, or the reason a URL failed.

This is a general pattern for **invisible primitive config**: maintainers or users shape the agent's reality through config that the agent cannot introspect.

## Use Case 2: Self-Implementing E2E Tests

### The problem

E2E tests today are either:
- **Human-written**: expensive to create, expensive to maintain, constantly stale
- **AI-generated each run**: accurate but slow and expensive (LLM cost per run)

### The third option: AI-generated once, runs for free, AI-maintained on failure

You describe what to test in natural language. The agent discovers the app and writes test code incrementally — navigating pages, finding elements, building assertions. Once written, the tests are code — they run without the agent, zero LLM cost per execution.

When a test fails, the agent comes back and reads the structured error. It determines:
- **Code bug** → fail loudly, report to the developer
- **Stale test** (UI changed, selector moved) → fix the test, re-run, verify

No human triaging flaky tests. No human updating selectors after a redesign.

### Why this proves the concept

- **Self-implementing**: agent discovers the app and builds test functions incrementally (`auth.test_login`, `checkout.test_empty_cart`, `profile.test_update_email`)
- **Code is memory**: tests persist as code, run for free across CI pipelines, no LLM involved at runtime
- **Self-healing**: agent maintains its own tests — the self-healing loop applied to test maintenance
- **Safety by construction**: the test agent can only read the app and write assertions. It cannot modify the application, the database, or anything outside the test scope

### POC built-ins (E2E variant)

| Namespace | Primitives | Safety note |
| :---- | :---- | :---- |
| `http` | `get`, `post`, `put`, `delete` | Scoped to target app URL only |
| `html` | `select`, `click`, `fill`, `submit`, `wait`, `text_of` | Browser interaction primitives |
| `assert` | `equals`, `contains`, `exists`, `not_exists`, `count` | Pure, self-validating |
| `text` | `split`, `join`, `contains`, `replace`, `match` | Pure functions |
| `list` | `map`, `filter`, `fold`, `length` | Pure functions |
| `map` | `get`, `set`, `keys`, `values` | Pure functions |
| `io` | `read`, `write` | Bounded to test output directory |

### Demo arc

```
"Test that a user can sign up, log in, and update their profile"

→ Agent navigates the app, discovers the signup flow
→ Writes auth.test_signup, auth.test_login, profile.test_update
→ Tests run in CI — fast, free, no LLM

Two weeks later: frontend redesign changes the login form
→ auth.test_login fails in CI
→ Agent reads the error, re-discovers the login page
→ Finds the new selectors, rewrites the test
→ Runs it, passes, saves
→ CI is green again — no developer touched a test file
```

## Technical Decisions

- **Interpreter language: Python.** Fast iteration while the language spec is still evolving. Easy parser libraries (`lark`, `pyparsing`, or hand-rolled recursive descent). Rust is a future option if the project proves out — Rust → Wasm is first-class, which aligns with the Wasm compilation target idea.

## POC Validation

### `ask` coroutine (scripts/ask_poc.py)

Validated that Python generators (`yield`/`.send()`) implement the `ask` mechanism correctly. Tested single-ask (`inbox_triage`) and multi-ask (`report_build`) flows, plus type validation rejection. State is replayed from start by feeding previous responses — generators can't be pickled, so no serialization needed.

### `spawn` + `ask` + `await_all` (scripts/spawn_poc.py)

Validated the full flow: orchestrator collects spawn requests up front, batches them into an instruction that tells the main agent to use sub-agents, sub-agents run in parallel (3 article bias analyses), results collected via `await_all`, then `ask` for curation by the main agent. The orchestrator generates the sub-agent instruction — the Lumon interpreter never calls an LLM API directly, it routes through the main agent's native sub-agent capability.

Key finding: the orchestrator must explicitly instruct the agent to spawn sub-agents (the agent won't do it unprompted). The `format_spawn_batch` function generates a structured instruction with the shared prompt, per-spawn contexts, and expected response format.

## Error Handling & Self-Healing

The agent is its own developer. Write, test, fix, iterate — no human in the loop for routine bugs.

### Structured errors

The interpreter returns full context on failure — not just "error on line 5" but: the function that failed, the inputs it received, the full stack trace, and which primitive ultimately raised. The agent reads this like a developer reads a traceback.

### Self-healing loop

Agent calls a function → it fails → agent reads the structured error → rewrites the implementation → tries again. Escalates to the user only when it can't self-resolve.

### Self-testing (FAST principles)

The agent writes tests alongside its implementations:

- **Fast** — tests run in milliseconds, no I/O, no network
- **Automated** — agent writes and runs them without human intervention
- **Self-validating** — pass/fail, no human interpretation needed
- **Timely** — written alongside or before the implementation

Test syntax is assertions within the language:

```
test inbox.summarize
  let sample = ["Buy milk", "Schedule dentist", "Read paper on agents"]
  let result = inbox.summarize(sample)
  assert list.length(result) <= 3
  assert text.contains(result, "milk") or text.contains(result, "dentist")
```

Test discovery: the interpreter finds everything in the `test.*` namespace automatically. When the agent modifies a function, the interpreter runs all tests that depend on it. **An implementation that breaks existing tests is rejected** — the agent doesn't get to deploy broken code.

## Versioning & Self-Upgrading

When the community updates the interface, the agent upgrades its own code.

### Flow

1. Community releases a new interface version — changed signatures, new namespaces, deprecations
2. Interpreter detects mismatch between interface version and local implementations
3. Agent reads the changelog, finds affected implementations, rewrites them
4. Agent runs its own tests to verify the migration
5. If tests fail, it iterates. If it can't fix something, it escalates to the user

### Changelog format

The interface ships with a machine-readable changelog the agent can parse:

```
changelog 2.1.0
  changed:
    inbox.read "Now returns a map with metadata instead of raw text"
      was: returns: text
      now: returns: map
  added:
    inbox.archive "Move processed items to archive"
  deprecated:
    inbox.mark_done "Use inbox.archive instead"
```

The agent is its own migration script. No human writing upgrade code.

## When to Write Functions (Agent Policy)

This is not a language design question — it's agent behavior, controlled via the agent's instruction file (e.g. `CLAUDE.md`). The language gives the ability; instructions give the policy.

### The optimization loop

1. **First time: do it inline.** The agent executes every step manually — no abstractions. This is the discovery phase. It figures out what works, how much context each step costs, where ambiguity lives.

2. **Extract when deterministic.** Once a sequence of steps is repeatable and unambiguous — same inputs always produce same outputs — the agent extracts it into a function. The function runs without LLM interpretation, saving tokens and context.

3. **Keep ambiguity in the agent, push determinism into code.** The agent handles judgment calls (what's relevant, how to triage, what to prioritize). Mechanical parts (parsing, transforming, filtering) become functions.

4. **Refactor when needs change.** If a function no longer fits, the agent rewrites it or breaks it into composable pieces. Tests catch regressions.

### Goals driving the policy

- **Reliability**: deterministic functions produce consistent results, no LLM variance
- **Performance**: functions reduce token consumption and context bloat
- **Emergent utility**: the agent only creates abstractions that are actually used — no speculative functions that never get called

Over time, more of the workflow becomes code and the agent's role shrinks to the genuinely ambiguous decisions. The agent naturally produces the most useful abstractions — the ones shaped by real usage.

## Open Design Questions

- ~~**Manifest hierarchy**~~: Resolved. Three-level discovery: `index.lumon` (namespace names, always in context) → `manifests/<ns>.lumon` (full signatures, on demand) → `impl/<ns>.lumon` (code, on call). See spec for details.
- ~~**Readability of nested constructs**~~: Resolved. Added `with/then/else` blocks (Elixir-inspired) for chaining fallible operations and `??` nil-coalescing operator for single none-checks. These eliminate most deep nesting from none-handling. See spec sections 4 and examples 8-9.
- ~~**Complex conditions (if/else)**~~: Resolved. Added guard clauses to `match` (`pattern if condition -> expr`). Guards cover multi-branch boolean conditions without needing `else if`. See spec section 4.
- ~~**How does the agent invoke functions?**~~: Resolved. The interpreter is a CLI (`lumon`). The agent uses Bash to run inline code (`lumon 'code'`), pipe from stdin, or execute files. Output is structured JSON to stdout. Interactive flows (ask/spawn) use `lumon respond '<json>'`. Discovery via `lumon browse [namespace]`, tests via `lumon test [namespace]`. No special tool registration — any agent with shell access can use it. See spec section 10.

## Prior Art & Landscape

### Languages designed for LLM agents

| Project | Year | What | Relevance | Gap vs. our concept |
| :---- | :---- | :---- | :---- | :---- |
| [Quasar](https://arxiv.org/abs/2506.12202) | 2025 | Python subset transpiled to purpose-built language for agent code actions. Automated parallelization, security features. | Closest to "language for LLMs." | Python subset, not pseudocode. No capability boundaries. |
| [Pel](https://arxiv.org/abs/2505.13453) | 2025 | Lisp-inspired language for LLM orchestration. Natural language conditions, auto-parallelization. | New language for agents. | Focused on orchestration, not capability boundaries. |
| [CoRE / AIOS](https://arxiv.org/abs/2405.06907) | 2024 | LLM-as-interpreter for pseudocode/natural language programs. | Pseudocode-like executable language. | Non-deterministic — LLM interprets at runtime. |
| [SudoLang](https://medium.com/javascript-scene/sudolang-a-powerful-pseudocode-programming-language-for-llms-d64d42aa719b) | 2023 | Pseudocode language for LLMs by Eric Elliott. | Pioneer in pseudocode-for-LLMs. | Structured prompting, no safety guarantees. |
| [Modus (Hypermode)](https://github.com/hypermodeinc/modus) | 2024 | Go/AssemblyScript compiled to Wasm for agent execution. | Wasm sandbox as capability boundary. | Agents don't write the code — developers do. |

### Safety & capability boundary approaches

| Project | Year | What | Relevance | Gap vs. our concept |
| :---- | :---- | :---- | :---- | :---- |
| [VeriGuard](https://arxiv.org/abs/2510.05156) (Google/DeepMind) | 2025 | Correct-by-construction code gen with formal verification. LLM generates code + proofs. | Safety by construction. | Wraps existing languages, doesn't build safety into primitives. |
| [AgentSpec](https://arxiv.org/abs/2503.18666) (ICSE 2026) | 2026 | DSL for runtime safety constraints on LLM agents. Trigger-predicate-enforcement rules. | DSL for constraining agents. | External policy layer, not the language the agent writes in. |
| [Agent Behavioral Contracts](https://arxiv.org/abs/2602.22302) | 2026 | Design-by-Contract for agents. Preconditions/postconditions/invariants. | Capability contracts. | Contracts wrap existing implementations, not baked into language. |
| [Colang / NeMo Guardrails](https://github.com/NVIDIA-NeMo/Guardrails) (NVIDIA) | 2023+ | Modeling language for LLM guardrails. Hybrid natural language + Python syntax. | DSL for agent boundaries. | Conversational AI focus, not general agent capabilities. |
| [Wasm sandboxing](https://developer.nvidia.com/blog/sandboxing-agentic-ai-workflows-with-webassembly/) (NVIDIA, CMU) | 2024+ | WebAssembly's memory isolation + capability-based security for agent code. | Capability boundary at VM level. | Infrastructure-level, not language-level. |
| [Anthropic sandbox](https://www.anthropic.com/engineering/claude-code-sandboxing) | 2025 | OS-level sandboxing (bubblewrap/seatbelt) for Claude Code. | Practical capability enforcement. | OS-level, not language-level. |

### Self-implementing agent systems

| Project | Year | What | Relevance | Gap vs. our concept |
| :---- | :---- | :---- | :---- | :---- |
| [Voyager](https://voyager.minedojo.org/) (NVIDIA/Stanford) | 2023 | Minecraft agent building ever-growing JavaScript skill library. Seminal self-implementing agent. | Agent writes and persists its own tools. | No safety boundary — arbitrary JS. |
| [Test-Time Tool Evolution](https://arxiv.org/abs/2601.07641) (NAACL 2025) | 2025 | Agents synthesize, verify, and refine Python tools during inference. Docker sandbox testing. | Self-implementing + verification. | Safety via Docker sandbox, not language design. |
| [Cradle](https://github.com/BAAI-Agents/Cradle) (BAAI, ICML 2025) | 2025 | General computer control agent with runtime skill curation. | Self-implementing at UI level. | No formal capability boundary. |

### Formal verification & governance

| Project | Year | What | Relevance |
| :---- | :---- | :---- | :---- |
| [Agent-C](https://arxiv.org/abs/2503.18666) | 2025 | Temporal safety constraints via SMT solving during code generation. | Enforcement at generation time, closer to safe-by-construction. |
| [Pro2Guard](https://arxiv.org/abs/2602.22302) | 2025 | Probabilistic model checking — predicts likely violations before they occur. | Proactive enforcement, not just reactive. |
| [Policy Cards](https://arxiv.org/html/2510.24383v1) | 2025 | Machine-interpretable governance that agents self-enforce. | Self-enforced constraints — agent reads its own rules. |
| [Genefication](https://www.mydistributed.systems/2025/01/genefication.html) | 2025 | Combining LLM code gen with formal verification (TLA+, Dafny, Alloy). | LLM generates, formal tools verify. |

### Key finding

**No existing project combines all three properties:**
1. A language designed for LLMs to write (Quasar, Pel)
2. Where language primitives define capability boundaries (Wasm's model)
3. With self-implementing agents whose code persists as memory (Voyager)

Our concept sits exactly in that gap.

### Practical insight from Microsoft research

[Microsoft found](https://devblogs.microsoft.com/all-things-azure/ai-coding-agents-domain-specific-languages/) that AI agents start below 20% accuracy on new DSLs but reach 85% with curated examples and explicit domain rules. Implication: the language must ship with extensive examples, or be close enough to pseudocode that the spec alone is sufficient.

## Ideas & Notes
<!-- Dump ideas, syntax sketches, competitor analysis here -->
- The "axioms in a formal system" framing: everything derivable from safe axioms is safe
- Could the interface double as documentation? Since descriptions are first-class, the interface is self-documenting
- Wasm could be a compilation target — inherit its security properties while keeping the pseudocode surface syntax
- VeriGuard's approach (generate code + proofs) could complement the language — agent writes in safe pseudocode AND generates verification conditions
- Voyager's skill library pattern is the closest to "code is memory" — but in an unsafe language. Ours would be the safe version of Voyager's model
