---
name: ask-spawn
description: When and how to use ask and spawn for resolving ambiguity in Lumon scripts. Scripts are autonomous subagents — never guess, always ask or spawn.
---

## Resolving ambiguity — always use ask and spawn

Lumon scripts are designed to run as autonomous subagents. When your code encounters ambiguity, **never guess or hardcode a default — use `ask` or `spawn` to resolve it**. This is the core contract: the script suspends, the orchestrator provides judgment, and execution resumes with a validated answer.

### When to use `ask`

Use `ask` whenever the next step requires a judgment call that the code cannot make deterministically. Common situations:

- **Ambiguous input**: the data could be interpreted multiple ways
- **Prioritization**: multiple valid options, no clear winner
- **Quality judgment**: "is this good enough?" or "which version is better?"
- **Missing information**: the code needs context only the agent has
- **Confirmation**: a destructive or irreversible action needs approval

```
implement tasks.process
  let items = io.read("tasks.md") |> parse_tasks
  match items
    :error(m) -> return :error(m)
    :ok(tasks) ->
      -- Don't guess priority — ask
      let prioritized = ask
        "These tasks need ordering. Which should I handle first?"
        context: tasks
        expects: {order: list, reasoning: text}

      return process_in_order(prioritized.order)
```

### When to use `spawn`

Use `spawn` when the reasoning task is **independent** and can be delegated to a sub-agent without the main agent's full context. Common situations:

- **Analysis**: "summarize this", "classify this", "extract facts from this"
- **Parallel work**: multiple items need the same kind of reasoning
- **Specialized judgment**: a task that benefits from focused context

```
implement docs.review
  let files = io.list_dir("docs/") |> unwrap
  let reviews = files
    |> list.map(fn(f) ->
      let content = io.read("docs/" + f) |> unwrap
      spawn
        "Review this document for accuracy and completeness"
        context: {file: f, content: content}
        expects: {issues: list, score: number, summary: text}
    )
    |> await_all

  -- Ask the main agent to make the final call
  let decision = ask
    "Here are the review results. Which docs need rewriting?"
    context: reviews
    expects: list

  return decision
```

### The pattern: code → spawn → ask → code

The canonical structure for any non-trivial script:

1. **Code** does mechanical work (read, parse, transform)
2. **`spawn`** delegates independent reasoning tasks in parallel
3. **`ask`** brings results to the main agent for judgment calls
4. **Code** acts on the decision (write, format, return)

Never collapse steps 2-3 into hardcoded logic. If a human would need to think about it, the script should `ask` or `spawn`.

### Anti-patterns to avoid

- **Hardcoding a choice** when the data is ambiguous — use `ask`
- **Returning raw data** and expecting the caller to figure it out — use `ask` to decide, then return the decision
- **Sequential reasoning** on independent items — use `spawn` + `await_all` for parallelism
- **Guessing a format or structure** from partial information — use `ask` to confirm
- **Swallowing ambiguity with a default** (e.g., `?? "unknown"`) when the agent should decide — use `ask` instead
