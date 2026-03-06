---
name: lumon
description: Perform a task by building reusable Lumon code that automates it end-to-end. Reuses existing code when available, fixes broken code in place, and extends the library rather than replacing it. Use this skill for any task the user gives you.
---

When given a task, your goal is to **build lasting automation** — not just produce a one-off result. Every task you complete should leave behind code that can repeat the task without regenerating anything.

## Phase 1: Discover existing code

Before writing anything, check if the task (or parts of it) is already automated.

1. **Browse the library** — scan `sandbox/lumon/manifests/` for functions related to the task
2. **Browse scripts** — scan `sandbox/scripts/` for a script that already does what's being asked
3. **Browse namespaces** — run `lumon --working-dir sandbox browse` to see all available capabilities (built-in and user-defined)

If a script already exists for this task, go to **Phase 4: Run**. If library functions exist that partially cover it, reuse them in your new script.

## Phase 2: Build the library layer

Identify the **reusable operations** the task requires. Each one becomes a library function — generic, parameterized, named for reuse.

For each function:

1. **Write the signature** to `sandbox/lumon/manifests/<namespace>.lumon`
   - Choose a namespace that groups related functions (e.g., `inbox`, `reports`, `tasks`)
   - Keep parameter names generic — `items` not `monday_tasks`, `path` not `inbox_file`

2. **Write the implementation** to `sandbox/lumon/impl/<namespace>.lumon`
   - Keep it under ~15 lines. If it's longer, split into helpers
   - Use `ask` for any decision that depends on context, judgment, or ambiguity
   - Use `spawn` for independent analysis that can run in parallel
   - Handle errors with `:ok`/`:error` tags — never let failures silently pass

3. **Test it** — write a `test` block in `sandbox/lumon/tests/<namespace>.lumon` and run it with `lumon --working-dir sandbox test <namespace>`

Build incrementally. Write one function, test it, then move on. Do not write the entire library at once.

## Phase 3: Build the script

Once the library functions work, compose them into a script in `sandbox/scripts/`.

The script is the **task-specific glue**. It:
- Calls library functions in the right order
- Uses `ask` to resolve decisions that vary each time the task runs (priorities, choices, confirmations)
- Uses `spawn` to delegate independent reasoning (analysis, classification, summarization)
- Returns a structured result

**The script must be self-contained** — running it from scratch should complete the entire task, including all `ask`/`spawn` interactions. A human or orchestrator replaying the script with the same responses should get the same result.

### Script naming

Name the script after the task it automates: `process_inbox.lumon`, `weekly_report.lumon`, `categorize_emails.lumon`. Anyone reading the `scripts/` directory should understand what each script does.

## Phase 4: Run

Run the script:

```bash
lumon --working-dir sandbox scripts/<task>.lumon
```

When the script suspends with `ask` or `spawn`, respond with your judgment. The orchestrator records your responses so the script can be replayed later.

### If the script fails

**Fix in place, never rewrite.** Read the error, identify the broken function, fix the implementation, and re-run. Specifically:

- **Type error** → fix the signature or implementation that has the wrong type
- **Undefined variable** → fix the implementation that references a missing binding
- **Runtime error from a library function** → fix that function's `implement` block
- **Wrong result** → adjust the implementation logic, add a missing edge case

After fixing, re-run the script to verify. Repeat until it completes successfully.

### If the failure is outside your control

Some failures aren't bugs in your code — they're problems with the interpreter or missing capabilities:

- **Interpreter bug** (parser rejects valid code, built-in behaves wrong) → file an issue in `sandbox/LUMON_ISSUES.md`
- **Missing capability** (need an external API, system tool) → file an issue in `sandbox/PLUGIN_ISSUES.md`

Then continue with other work that doesn't depend on the blocked capability.

### If you need a new capability mid-task

Don't abandon the current approach. Instead:

1. Add the new function to the library (manifest + impl + test)
2. Update the script to use it
3. Continue where you left off

This is **extending**, not replacing. The existing functions stay. The script grows.

## Rules

- **Always write code to `.lumon` files before running — never pass inline code to the CLI.** Use `lumon --working-dir sandbox scripts/<file>.lumon` or `lumon --working-dir sandbox test <namespace>`. Inline commands (`lumon --working-dir sandbox '<code>'`) are only acceptable for one-off debugging that won't be reused.
- **Never hardcode task-specific values in library functions.** Pass them as parameters. The function `reports.summarize(items, format)` is reusable; `reports.summarize_monday_standup()` is not.
- **Never skip the library layer.** Even if a task seems simple, write a function for it. Next time the same operation is needed, the function is already there.
- **Never delete working code.** If a function's behavior needs to change, add a parameter or write a new function. Other scripts may depend on the existing behavior.
- **Always use `ask` for ambiguous decisions in scripts.** The script should produce the same result when replayed with the same responses — no implicit assumptions.
- **Always test library functions before using them in scripts.** A broken function wastes time debugging the script.

## Example: processing an inbox

**Task**: "Process my inbox and summarize the action items."

**Phase 1**: Check `sandbox/scripts/` — no `process_inbox.lumon` exists. Check manifests — no `inbox` namespace yet.

**Phase 2**: Build library functions:
- `inbox.read(path)` → reads a markdown file, extracts list items
- `inbox.categorize(items)` → uses `spawn` to classify each item in parallel
- `inbox.summarize(categorized)` → uses `ask` to get the agent's summary priorities

**Phase 3**: Write `sandbox/scripts/process_inbox.lumon`:
```
let raw = inbox.read("INBOX.md")
match raw
  :error(m) -> return :error(m)
  :ok(items) ->
    let categorized = inbox.categorize(items)
    let summary = inbox.summarize(categorized)
    let result = io.write("SUMMARY.md", summary)
    return result
```

**Phase 4**: Run it. Respond to `spawn` prompts (categorization) and `ask` prompts (summary priorities). The script completes. Next time, just run it again.
