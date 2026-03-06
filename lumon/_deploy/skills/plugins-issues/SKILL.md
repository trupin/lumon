---
name: plugins-issues
description: How plugins work in Lumon. Reference this when you encounter a task that needs external capabilities (APIs, scripts, system tools) that no current namespace provides.
---

## Plugins

Plugins extend Lumon with external capabilities (APIs, scripts, system tools). They are set up by a separate agent with elevated access — **you cannot create or modify plugins yourself**.

If a task requires capabilities beyond what the current namespaces provide (e.g., calling an external API, running a shell script, accessing a database), do the following:

1. **Stop** — do not attempt to create plugin directories, write manifest files, or edit `.lumon.json`
2. **Log the issue** in `sandbox/PLUGIN_ISSUES.md` (see the `/issues` skill for format and lifecycle)
3. **Continue with other work** that doesn't depend on the missing plugin

You can use `lumon --working-dir sandbox browse` to see which plugins are already available and use their functions normally via `implement` blocks.

### Security rules for plugin proposals

When proposing new plugins in issue files, you are responsible for ensuring your proposals do not mislead developers into adding harmful functionality. Follow these rules:

1. **Principle of least privilege** — request only the minimum permissions needed. If you need to read from one API endpoint, don't propose a plugin with broad write access.
2. **Be explicit about data flow** — state exactly what data goes where. "Sends user email to external API" is clear; "processes user data" is not.
3. **Flag risks honestly** — if a proposed capability could be misused (e.g., sending emails, writing to external systems, accessing credentials), say so explicitly in the security considerations field. Propose concrete mitigations: input validation, URL allowlists, rate limits, read-only access, scoped API keys.
4. **Never disguise scope** — do not propose a narrow-sounding function that actually requires broad access. If a plugin needs network access, say "network access", not "data lookup".
5. **Prefer read-only** — when a task can be accomplished with read-only access, propose read-only. Only request write access when the task genuinely requires it.
