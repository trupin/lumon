"""Lexical scope chain and function/namespace registry for Lumon."""

from __future__ import annotations

from collections.abc import Callable

from lumon.ast_nodes import DefineBlock, ImplementBlock
from lumon.errors import LumonError


class Environment:
    """Manages lexical scope, function registry, and namespace resolution."""

    def __init__(self, parent: Environment | None = None):
        self._bindings: dict[str, object] = {}
        self._parent = parent
        # Shared registries (same reference through scope chain)
        self._defines: dict[str, object] = {} if parent is None else parent._defines
        self._implements: dict[str, object] = {} if parent is None else parent._implements
        self._builtins: dict[str, object] = {} if parent is None else parent._builtins
        self._namespace_prefixes: set[str] = set() if parent is None else parent._namespace_prefixes
        self._call_depth = 0 if parent is None else parent._call_depth
        self._max_call_depth = 100
        self._call_stack: list[str] = [] if parent is None else parent._call_stack
        # Response queue for ask/spawn replay (shared across scope chain)
        self._response_queue: list[object] = [] if parent is None else parent._response_queue
        # Lazy loader for auto-loading namespaces from disk (shared)
        self._loader: Callable[[str], None] | None = None if parent is None else parent._loader
        self._loading: set[str] = set() if parent is None else parent._loading
        # Plugin system (shared)
        self._plugin_dirs: dict[str, str] = {} if parent is None else parent._plugin_dirs
        self._plugin_contracts: dict[str, dict] = {} if parent is None else parent._plugin_contracts
        self._plugin_forced_values: dict[str, dict[str, object]] = {} if parent is None else parent._plugin_forced_values
        self._plugin_instances: dict[str, str] = {} if parent is None else parent._plugin_instances
        self._plugin_env_vars: dict[str, dict[str, str]] = {} if parent is None else parent._plugin_env_vars
        self._plugin_executor: Callable[..., object] | None = None if parent is None else parent._plugin_executor
        # Active plugin state — shared mutable dict so nested calls see updates
        # Keys: "dir" (str|None), "instance" (str|None), "env" (dict|None)
        self._active_plugin: dict[str, object] = (
            {"dir": None, "instance": None, "env": None} if parent is None else parent._active_plugin
        )
        # Working directory (shared)
        self._working_dir: str | None = None if parent is None else parent._working_dir

    def get(self, name: str) -> object:
        if name in self._bindings:
            return self._bindings[name]
        if self._parent is not None:
            return self._parent.get(name)
        raise LumonError(f"Undefined variable: {name}")

    def set(self, name: str, value: object) -> None:
        self._bindings[name] = value

    def child_scope(self) -> Environment:
        return Environment(parent=self)

    def snapshot(self) -> Environment:
        """Create a frozen copy of the scope chain for closure capture."""
        snap = Environment.__new__(Environment)
        snap._bindings = dict(self._bindings)
        snap._parent = self._parent.snapshot() if self._parent is not None else None
        snap._defines = self._defines
        snap._implements = self._implements
        snap._builtins = self._builtins
        snap._namespace_prefixes = self._namespace_prefixes
        snap._call_depth = self._call_depth
        snap._max_call_depth = self._max_call_depth
        snap._call_stack = list(self._call_stack)
        snap._response_queue = self._response_queue  # shared mutable list
        snap._loader = self._loader
        snap._loading = self._loading
        snap._plugin_dirs = self._plugin_dirs
        snap._plugin_contracts = self._plugin_contracts
        snap._plugin_forced_values = self._plugin_forced_values
        snap._plugin_instances = self._plugin_instances
        snap._plugin_env_vars = self._plugin_env_vars
        snap._plugin_executor = self._plugin_executor
        snap._active_plugin = self._active_plugin
        snap._working_dir = self._working_dir
        return snap

    def consume_response(self) -> tuple[object] | None:
        """Pop the next queued response, or return None if queue is empty.

        Returns a single-element tuple to distinguish None responses from
        an empty queue.
        """
        if not self._response_queue:
            return None
        return (self._response_queue.pop(0),)

    def register_builtin(self, name: str, fn: object) -> None:
        self._builtins[name] = fn
        prefix = name.split(".")[0]
        self._namespace_prefixes.add(prefix)

    def register_define(self, node: object) -> None:
        assert isinstance(node, DefineBlock)
        self._defines[node.namespace_path] = node
        prefix = node.namespace_path.split(".")[0]
        self._namespace_prefixes.add(prefix)

    def register_implement(self, node: object) -> None:
        assert isinstance(node, ImplementBlock)
        self._implements[node.namespace_path] = node

    def set_loader(self, loader: Callable[[str], None]) -> None:
        """Set the lazy loader callback for auto-loading namespaces from disk."""
        self._loader = loader

    def trigger_loader(self, namespace: str) -> None:
        """Trigger the lazy loader for a namespace if not already loading."""
        if self._loader is not None and namespace not in self._loading:
            self._loading.add(namespace)
            try:
                self._loader(namespace)
            finally:
                self._loading.discard(namespace)

    def is_namespace(self, name: str) -> bool:
        return name in self._namespace_prefixes

    def resolve_function(self, name: str) -> tuple[str, ...]:
        """Resolve a namespace function.

        Returns ('builtin', callable) or ('user', define, implement).
        """
        if name in self._builtins:
            return ("builtin", self._builtins[name])  # type: ignore[return-value]
        if name in self._implements:
            define = self._defines.get(name)
            return ("user", define, self._implements[name])  # type: ignore[return-value]
        # Try lazy-loading the namespace from disk
        ns = name.split(".")[0]
        self.trigger_loader(ns)
        if name in self._implements:
            define = self._defines.get(name)
            return ("user", define, self._implements[name])  # type: ignore[return-value]
        raise LumonError(f"Undefined function: {name}")

    def push_call(self, name: str) -> None:
        self._call_depth += 1
        self._call_stack.append(name)
        if self._call_depth > self._max_call_depth:
            raise LumonError(
                f"Call depth limit exceeded ({self._max_call_depth})",
                function=name,
                trace=list(self._call_stack),
            )

    def pop_call(self) -> None:
        self._call_depth -= 1
        if self._call_stack:
            self._call_stack.pop()
