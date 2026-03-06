"""Parse Lumon source code into AST nodes using lark."""

from __future__ import annotations

from collections.abc import Generator, Iterator

from lark import Lark, Token, Transformer, v_args
from lark.indenter import DedentError, Indenter

from lumon.ast_nodes import (
    AskExpr,
    AssertStatement,
    AsyncExpr,
    AwaitAllExpr,
    AwaitExpr,
    BinaryOp,
    BindPattern,
    Block,
    BoolLiteral,
    DefineBlock,
    FieldAccess,
    FunctionCall,
    IfElseExpr,
    IfStatement,
    ImplementBlock,
    IndexAccess,
    InterpolatedText,
    Lambda,
    LambdaCall,
    LetBinding,
    ListLiteral,
    ListPattern,
    LiteralPattern,
    MapEntry,
    MapLiteral,
    MapPattern,
    MatchArm,
    MatchExpr,
    NoneLiteral,
    NumberLiteral,
    ParamDef,
    PipeOp,
    Program,
    ReturnStatement,
    SpawnExpr,
    SpreadEntry,
    TagLiteral,
    TagPattern,
    TestBlock,
    TextLiteral,
    UnaryOp,
    VarRef,
    WildcardPattern,
    WithExpr,
)
from lumon.errors import LumonError
from lumon.grammar import GRAMMAR


class LumonIndenter(Indenter):
    NL_type = "_NL"  # type: ignore[assignment]
    OPEN_PAREN_types: list[str] = ["LPAR", "LSQB", "LBRACE"]  # type: ignore[assignment]
    CLOSE_PAREN_types: list[str] = ["RPAR", "RSQB", "RBRACE"]  # type: ignore[assignment]
    INDENT_type = "_INDENT"  # type: ignore[assignment]
    DEDENT_type = "_DEDENT"  # type: ignore[assignment]
    tab_len = 2  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        # True after seeing ARROW while paren_level > 0 — next _NL may start a lambda body
        self._arrow_pending: bool = False
        # Stack of (base_indent, paren_level_at_entry) for lambda bodies inside parens
        self._lambda_body_stack: list[tuple[int, int]] = []

    def process(self, stream: Iterator[Token]) -> Generator[Token, None, None]:  # type: ignore[override]
        self.paren_level = 0
        self.indent_level = [0]
        self._arrow_pending = False
        self._lambda_body_stack = []
        return self._process(stream)

    def _process(self, stream: Iterator[Token]) -> Generator[Token, None, None]:  # type: ignore[override]
        token = None
        for token in stream:
            if token.type == self.NL_type:
                yield from self.handle_NL(token)
            else:
                # If we were waiting for a lambda body but got a non-NL token,
                # it's an inline lambda — clear the pending flag.
                if self._arrow_pending and token.type not in self.OPEN_PAREN_types:
                    self._arrow_pending = False

                yield token

                if token.type in self.OPEN_PAREN_types:
                    self.paren_level += 1
                elif token.type in self.CLOSE_PAREN_types:
                    self.paren_level -= 1
                    assert self.paren_level >= 0
                elif token.type == "ARROW" and self.paren_level > 0:
                    self._arrow_pending = True

        # End of stream: close any remaining lambda body indents, then top-level
        while self._lambda_body_stack:
            self._lambda_body_stack.pop()
            self.indent_level.pop()
            yield Token.new_borrow_pos(self.DEDENT_type, '', token) if token else Token(self.DEDENT_type, '')

        while len(self.indent_level) > 1:
            self.indent_level.pop()
            yield Token.new_borrow_pos(self.DEDENT_type, '', token) if token else Token(self.DEDENT_type, '')

        assert self.indent_level == [0], self.indent_level

    def _active_lambda_paren_level(self) -> int | None:
        """Return the paren_level of the innermost active lambda body, or None."""
        if self._lambda_body_stack:
            return self._lambda_body_stack[-1][1]
        return None

    def handle_NL(self, token: Token) -> Iterator[Token]:
        indent_str = token.rsplit('\n', 1)[1]
        indent = indent_str.count(' ') + indent_str.count('\t') * self.tab_len

        lam_paren = self._active_lambda_paren_level()

        # Case 1: Arrow pending — check if this NL starts a lambda block body
        if self._arrow_pending:
            self._arrow_pending = False
            if indent > self.indent_level[-1]:
                # Push lambda body: record base indent and paren level
                self._lambda_body_stack.append((self.indent_level[-1], self.paren_level))
                self.indent_level.append(indent)
                yield Token.new_borrow_pos(self.NL_type, token, token)
                yield Token.new_borrow_pos(self.INDENT_type, indent_str, token)
            else:
                # Not indented — inline lambda that just had a newline before expr.
                # Suppress the NL (we're inside parens).
                return
            return

        # Case 2: Inside a lambda body at its paren level — track indent normally
        if lam_paren is not None and self.paren_level == lam_paren:
            base_indent = self._lambda_body_stack[-1][0]

            # If we've dedented to or below the base, close the lambda body
            if indent <= base_indent:
                # Close all lambda bodies that are at or above this indent
                while self._lambda_body_stack and indent <= self._lambda_body_stack[-1][0]:
                    self._lambda_body_stack.pop()
                    self.indent_level.pop()
                    yield Token.new_borrow_pos(self.NL_type, token, token)
                    yield Token.new_borrow_pos(self.DEDENT_type, indent_str, token)
                # After closing lambda body, we're back in parens — suppress this NL
                return

            # Still inside the lambda body — normal indent/dedent tracking
            yield Token.new_borrow_pos(self.NL_type, token, token)

            if indent > self.indent_level[-1]:
                self.indent_level.append(indent)
                yield Token.new_borrow_pos(self.INDENT_type, indent_str, token)
            else:
                dedented = False
                while indent < self.indent_level[-1]:
                    self.indent_level.pop()
                    yield Token.new_borrow_pos(self.DEDENT_type, indent_str, token)
                    dedented = True

                if indent != self.indent_level[-1]:
                    raise DedentError(
                        'Unexpected dedent to column %s. Expected dedent to %s'
                        % (indent, self.indent_level[-1])
                    )

                if dedented:
                    yield Token.new_borrow_pos(self.NL_type, '', token)
            return

        # Case 3: Inside parens but not in a lambda body (or nested deeper) — suppress
        if self.paren_level > 0:
            return

        # Case 4: Top-level — normal indentation handling
        yield token  # _NL token

        if indent > self.indent_level[-1]:
            self.indent_level.append(indent)
            yield Token.new_borrow_pos(self.INDENT_type, indent_str, token)
        else:
            dedented = False
            while indent < self.indent_level[-1]:
                self.indent_level.pop()
                yield Token.new_borrow_pos(self.DEDENT_type, indent_str, token)
                dedented = True

            if indent != self.indent_level[-1]:
                raise DedentError(
                    'Unexpected dedent to column %s. Expected dedent to %s'
                    % (indent, self.indent_level[-1])
                )

            # After dedent(s), emit an extra _NL so the grammar has a
            # statement separator after the block's _NL _DEDENT is consumed.
            if dedented:
                yield Token.new_borrow_pos(self.NL_type, '', token)


def _preprocess(source: str) -> str:
    """Pre-process source code before lexing.

    - Join pipe continuation lines (lines starting with |>) to previous line.
    """
    lines = source.split("\n")
    result: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("|>") and result:
            result[-1] = result[-1] + " " + stripped
        else:
            result.append(line)
    return "\n".join(result)


def _unescape_string(s: str) -> str:
    """Process escape sequences in a Lumon string (without interpolation)."""
    result: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            c = s[i + 1]
            if c == "n":
                result.append("\n")
                i += 2
            elif c == "t":
                result.append("\t")
                i += 2
            elif c == "\\":
                result.append("\\")
                i += 2
            elif c == '"':
                result.append('"')
                i += 2
            elif c == "(":
                # This shouldn't happen in non-interpolated strings
                result.append("\\(")
                i += 2
            else:
                result.append(s[i])
                i += 1
        else:
            result.append(s[i])
            i += 1
    return "".join(result)


def _parse_interpolated_string(raw: str) -> TextLiteral | InterpolatedText:
    """Parse a string that may contain \\(expr) interpolation sequences.

    Returns TextLiteral if no interpolation, InterpolatedText otherwise.
    """
    # Check if there are any interpolations
    if "\\(" not in raw:
        return TextLiteral(_unescape_string(raw))

    parts: list[object] = []
    i = 0
    current_text: list[str] = []

    while i < len(raw):
        if raw[i] == "\\" and i + 1 < len(raw):
            c = raw[i + 1]
            if c == "(":
                # Flush current text
                if current_text:
                    parts.append("".join(current_text))
                    current_text = []
                # Find matching closing paren
                depth = 1
                start = i + 2
                j = start
                while j < len(raw) and depth > 0:
                    if raw[j] == "(":
                        depth += 1
                    elif raw[j] == ")":
                        depth -= 1
                    j += 1
                expr_code = raw[start : j - 1]
                # Parse the expression
                expr_ast = parse(f"return {expr_code}")
                # Extract the expression from the return statement
                if isinstance(expr_ast, Program) and expr_ast.statements:
                    stmt = expr_ast.statements[0]
                    if isinstance(stmt, ReturnStatement):
                        parts.append(stmt.value)
                i = j
            elif c == "n":
                current_text.append("\n")
                i += 2
            elif c == "t":
                current_text.append("\t")
                i += 2
            elif c == "\\":
                current_text.append("\\")
                i += 2
            elif c == '"':
                current_text.append('"')
                i += 2
            else:
                current_text.append(raw[i])
                i += 1
        else:
            current_text.append(raw[i])
            i += 1

    if current_text:
        parts.append("".join(current_text))

    # If no interpolation was actually found, return plain text
    if len(parts) == 1 and isinstance(parts[0], str):
        return TextLiteral(parts[0])

    return InterpolatedText(tuple(parts))


@v_args(inline=True)
class LumonTransformer(Transformer):
    """Transform lark parse tree into Lumon AST nodes."""

    # --- Literals ---

    def number_lit(self, token: Token) -> NumberLiteral:
        s = str(token)
        if "." in s:
            return NumberLiteral(float(s))
        return NumberLiteral(int(s))

    def simple_string(self, token: Token) -> TextLiteral | InterpolatedText:
        raw = str(token)[1:-1]  # strip quotes
        return _parse_interpolated_string(raw)

    def interp_string(self, token: Token) -> TextLiteral | InterpolatedText:
        raw = str(token)[1:-1]
        return _parse_interpolated_string(raw)

    def true_lit(self) -> BoolLiteral:
        return BoolLiteral(True)

    def false_lit(self) -> BoolLiteral:
        return BoolLiteral(False)

    def none_lit(self) -> NoneLiteral:
        return NoneLiteral()

    def list_literal(self, *elements: object) -> ListLiteral:
        return ListLiteral(elements)

    def map_literal(self, *entries: object) -> MapLiteral:
        return MapLiteral(entries)

    def kv_entry(self, key: Token, value: object) -> MapEntry:
        return MapEntry(str(key), value)

    def spread_entry(self, expr: object) -> SpreadEntry:
        return SpreadEntry(expr)

    def tag_literal(self, name: Token | str, *payload: object) -> TagLiteral:
        p = payload[0] if payload else None
        return TagLiteral(str(name), p)

    # --- Bindings ---

    def let_binding(self, name: Token | str, value: object) -> LetBinding:
        return LetBinding(str(name), value)

    def return_stmt(self, value: object) -> ReturnStatement:
        return ReturnStatement(value)

    def var_ref(self, name: Token | str) -> VarRef:
        return VarRef(str(name))

    # --- Operators ---

    def not_op(self, operand: object) -> UnaryOp:
        return UnaryOp("not", operand)

    def neg_op(self, *args: object) -> UnaryOp:
        # args may include the MINUS token; the operand is always last
        return UnaryOp("-", args[-1])

    def comparison_expr(self, *args: object) -> object:
        return self._left_assoc_binary(args)

    def add_expr(self, *args: object) -> object:
        return self._left_assoc_binary(args)

    def mul_expr(self, *args: object) -> object:
        return self._left_assoc_binary(args)

    def nil_coalesce_expr(self, *args: object) -> object:
        # Filter out DBLQUEST tokens
        args = tuple(a for a in args if not (isinstance(a, Token) and a.type == "DBLQUEST"))
        if len(args) == 1:
            return args[0]
        result = args[0]
        for i in range(1, len(args)):
            result = BinaryOp("??", result, args[i])
        return result

    def or_expr(self, *args: object) -> object:
        if len(args) == 1:
            return args[0]
        result = args[0]
        for i in range(1, len(args)):
            result = BinaryOp("or", result, args[i])
        return result

    def and_expr(self, *args: object) -> object:
        if len(args) == 1:
            return args[0]
        result = args[0]
        for i in range(1, len(args)):
            result = BinaryOp("and", result, args[i])
        return result

    def _left_assoc_binary(self, args: tuple[object, ...]) -> object:
        if len(args) == 1:
            return args[0]
        result = args[0]
        i = 1
        while i < len(args):
            op = str(args[i])
            right = args[i + 1]
            result = BinaryOp(op, result, right)
            i += 2
        return result

    # --- Postfix access ---

    def postfix_expr(self, primary: object, *accesses: object) -> object:
        result = primary
        for access in accesses:
            result = access(result)  # type: ignore[operator]
        return result

    def dot_access(self, name: Token | str):
        field = str(name)
        def apply(obj: object) -> FieldAccess:
            return FieldAccess(obj, field)
        return apply

    def index_access(self, expr: object):
        def apply(obj: object) -> IndexAccess:
            return IndexAccess(obj, expr)
        return apply

    # --- Pipe ---

    def pipe_expr(self, *args: object) -> object:
        # Filter out PIPE tokens (named terminals are passed through)
        args = tuple(a for a in args if not (isinstance(a, Token) and a.type == "PIPE"))
        if len(args) == 1:
            return args[0]
        result = args[0]
        for i in range(1, len(args)):
            result = PipeOp(result, args[i])
        return result

    def var_ref_target(self, name: Token | str) -> VarRef:
        return VarRef(str(name))

    def namespace_ref(self, ns_path: object) -> object:
        return ns_path

    # --- Function calls ---

    def namespace_path(self, *names: Token) -> str:
        return ".".join(str(n) for n in names)

    def function_call(self, ns_path: str, *args_nodes: object) -> FunctionCall:
        # args_nodes might contain an 'arguments' node or be empty
        args = self._extract_args(args_nodes)
        return FunctionCall(ns_path, args)

    def local_call(self, name: Token | str, *args_nodes: object) -> FunctionCall | LambdaCall:
        args = self._extract_args(args_nodes)
        n = str(name)
        return LambdaCall(VarRef(n), args)

    def arguments(self, *args: object) -> tuple[object, ...]:
        return args

    def _extract_args(self, args_nodes: tuple[object, ...]) -> tuple[object, ...]:
        if not args_nodes:
            return ()
        if len(args_nodes) == 1 and isinstance(args_nodes[0], tuple):
            return args_nodes[0]
        return args_nodes

    # --- Lambda ---

    def lambda_expr(self, *children: object) -> Lambda:
        # Filter out ARROW and FN_KW tokens
        children = tuple(c for c in children if not (isinstance(c, Token) and c.type in ("ARROW", "FN_KW")))
        # children: [params?, body]
        if len(children) == 1:
            # No params
            return Lambda((), children[0])
        params_node = children[0]
        body = children[1]
        if isinstance(params_node, tuple):
            return Lambda(params_node, body)
        # Single param
        return Lambda((str(params_node),), body)

    def params(self, *names: Token) -> tuple[str, ...]:
        return tuple(str(n) for n in names)

    def lambda_inline(self, expr: object) -> object:
        return expr

    def lambda_block(self, block: object) -> object:
        return block

    # --- Block ---

    def block(self, *statements: object) -> Block:
        return Block(tuple(s for s in statements if s is not None))

    def impl_body(self, *statements: object) -> tuple[object, ...]:
        return tuple(s for s in statements if s is not None)

    # --- Control flow ---

    def inline_if_expr(self, condition: object, then_expr: object, else_expr: object) -> IfElseExpr:
        return IfElseExpr(condition, then_expr, else_expr)

    def if_stmt(self, condition: object, body: object, *else_parts: object) -> IfStatement:
        else_body = else_parts[0] if else_parts else None
        return IfStatement(condition, body, else_body)

    def else_clause(self, body: object) -> object:
        return body

    # --- Match ---

    def match_expr(self, subject: object, *arms: object) -> MatchExpr:
        return MatchExpr(subject, tuple(arms))

    def match_arm(self, pattern: object, *rest: object) -> MatchArm:
        # Filter out ARROW tokens
        rest = tuple(r for r in rest if not (isinstance(r, Token) and r.type == "ARROW"))
        guard = None
        body = rest[-1]
        if len(rest) > 1:
            guard = rest[0]
        return MatchArm(pattern, guard, body)

    def guard(self, expr: object) -> object:
        return expr

    def arm_inline(self, expr: object) -> object:
        return expr

    def arm_block(self, block: object) -> object:
        return block

    # --- Patterns ---

    def wildcard_pattern(self) -> WildcardPattern:
        return WildcardPattern()

    def bind_pattern(self, name: Token | str) -> BindPattern:
        return BindPattern(str(name))

    def lit_pattern_num(self, token: Token) -> LiteralPattern:
        s = str(token)
        if "." in s:
            return LiteralPattern(float(s))
        return LiteralPattern(int(s))

    def lit_pattern_str(self, token: Token) -> LiteralPattern:
        return LiteralPattern(_unescape_string(str(token)[1:-1]))

    def lit_pattern_true(self) -> LiteralPattern:
        return LiteralPattern(True)

    def lit_pattern_false(self) -> LiteralPattern:
        return LiteralPattern(False)

    def lit_pattern_none(self) -> LiteralPattern:
        return LiteralPattern(None)

    def tag_pattern(self, name: Token | str, *payload: object) -> TagPattern:
        p = payload[0] if payload else None
        return TagPattern(str(name), p)

    def map_pattern(self, *entries: object) -> MapPattern:
        return MapPattern(tuple(entries))  # type: ignore[arg-type]

    def map_pattern_entry(self, key: Token, pattern: object) -> tuple[str, object]:
        return (str(key), pattern)

    def list_pattern(self, *elements: object) -> ListPattern:
        rest_name = None
        patterns: list[object] = []
        for e in elements:
            if isinstance(e, str) and e.startswith("...REST:"):
                rest_name = e[8:]
            else:
                patterns.append(e)
        return ListPattern(tuple(patterns), rest_name)

    def rest_pattern(self, name: Token | str) -> str:
        return f"...REST:{name}"

    # --- With / Then / Else ---

    def with_expr(self, *children: object) -> WithExpr:
        # children: [with_bindings..., then_block, else_block]
        bindings: list[tuple[str, object]] = []
        blocks: list[object] = []
        for child in children:
            if isinstance(child, tuple) and len(child) == 2 and isinstance(child[0], str):
                bindings.append(child)
            else:
                blocks.append(child)
        return WithExpr(tuple(bindings), blocks[0], blocks[1])

    def with_binding(self, name: Token | str, expr: object) -> tuple[str, object]:
        return (str(name), expr)

    # --- Ask / Spawn ---

    def ask_expr(self, body: object) -> AskExpr:
        return body  # type: ignore[return-value]

    def ask_body(self, prompt: Token, fields: object) -> AskExpr:
        prompt_str = _unescape_string(str(prompt)[1:-1])
        if isinstance(fields, AskExpr):
            return AskExpr(TextLiteral(prompt_str), fields.context, fields.expects)
        return AskExpr(TextLiteral(prompt_str))

    def ask_fields(self, *children: object) -> AskExpr:
        context = None
        expects = None
        for child in children:
            if isinstance(child, tuple):
                if child[0] == "context":
                    context = child[1]
                elif child[0] == "expects":
                    expects = child[1]
        return AskExpr(None, context, expects)

    def ask_context(self, expr: object) -> tuple[str, object]:
        return ("context", expr)

    def ask_expects(self, type_expr: object) -> tuple[str, object]:
        return ("expects", type_expr)

    def spawn_expr(self, body: object) -> SpawnExpr:
        return body  # type: ignore[return-value]

    def spawn_body(self, prompt: Token, fields: object) -> SpawnExpr:
        prompt_str = _unescape_string(str(prompt)[1:-1])
        if isinstance(fields, SpawnExpr):
            return SpawnExpr(TextLiteral(prompt_str), fields.context, fields.fork, fields.expects)
        return SpawnExpr(TextLiteral(prompt_str))

    def spawn_fields(self, *children: object) -> SpawnExpr:
        context = None
        fork = None
        expects = None
        for child in children:
            if isinstance(child, tuple):
                if child[0] == "context":
                    context = child[1]
                elif child[0] == "fork":
                    fork = child[1]
                elif child[0] == "expects":
                    expects = child[1]
        return SpawnExpr(None, context, fork, expects)

    def spawn_context(self, expr: object) -> tuple[str, object]:
        return ("context", expr)

    def spawn_fork(self, expr: object) -> tuple[str, object]:
        return ("fork", expr)

    def spawn_expects(self, type_expr: object) -> tuple[str, object]:
        return ("expects", type_expr)

    # --- Async / Await ---

    def async_expr(self, expr: object) -> AsyncExpr:
        return AsyncExpr(expr)

    def await_expr(self, expr: object) -> AwaitExpr:
        return AwaitExpr(expr)

    def await_all_expr(self, expr: object) -> AwaitAllExpr:
        return AwaitAllExpr(expr)

    # --- Type expressions (stored as strings or dicts for now) ---

    def type_union_node(self, *types: object) -> object:
        if len(types) == 1:
            return types[0]
        return {"union": list(types)}

    def type_name(self, name: Token | str) -> str:
        return str(name)

    def type_parameterized(self, *children: object) -> dict:
        # Filter out LT/GT tokens from type_parameterized: IDENT LT type_expr GT
        filtered = [c for c in children if not (isinstance(c, Token) and c.type in ("LT", "GT"))]
        return {str(filtered[0]): filtered[1]}

    def struct_type(self, *children: object) -> dict:
        fields = {}
        i = 0
        while i < len(children):
            fields[str(children[i])] = children[i + 1]
            i += 2
        return {"struct": fields}

    def tag_type(self, name: Token | str, *payload: object) -> dict:
        if payload:
            return {"tag": str(name), "payload": payload[0]}
        return {"tag": str(name)}

    def fn_type(self, *children: object) -> dict:
        # Filter out ARROW and FN_KW tokens
        children = tuple(c for c in children if not (isinstance(c, Token) and c.type in ("ARROW", "FN_KW")))
        return {"fn": list(children[:-1]), "returns": children[-1]}

    # --- Define / Implement ---

    def description(self, token: Token) -> str:
        return _unescape_string(str(token)[1:-1])

    def define_block(self, ns_path: str, desc: str, *rest: object) -> DefineBlock:
        params: tuple[object, ...] = ()
        return_type = None
        return_desc = ""
        for item in rest:
            if isinstance(item, list):
                params = tuple(item)
            elif isinstance(item, tuple) and len(item) == 2:
                return_type, return_desc = item
        return DefineBlock(ns_path, desc, params, return_type, return_desc)

    def takes_clause(self, *param_defs: object) -> list[object]:
        return list(param_defs)

    def param_def(self, name: Token | str, type_expr: object, desc: Token, *default: object) -> ParamDef:
        d = default[0] if default else None
        return ParamDef(str(name), type_expr, _unescape_string(str(desc)[1:-1]), d)

    def returns_clause(self, type_expr: object, desc: Token) -> tuple[object, str]:
        return (type_expr, _unescape_string(str(desc)[1:-1]))

    def implement_block(self, ns_path: str, body: tuple[object, ...]) -> ImplementBlock:
        return ImplementBlock(ns_path, body)

    # --- Test / Assert ---

    def test_block(self, ns_path: str, body: tuple[object, ...]) -> TestBlock:
        return TestBlock(ns_path, body)

    def test_body(self, *statements: object) -> tuple[object, ...]:
        return tuple(s for s in statements if s is not None)

    def assert_stmt(self, expr: object) -> AssertStatement:
        return AssertStatement(expr)

    # --- Program ---

    def start(self, *statements: object) -> Program:
        return Program(tuple(s for s in statements if s is not None))


_parser: Lark | None = None  # pylint: disable=invalid-name


def _get_parser() -> Lark:
    global _parser
    if _parser is None:
        _parser = Lark(
            GRAMMAR,
            parser="earley",
            ambiguity="resolve",
            postlex=LumonIndenter(),
            maybe_placeholders=False,
        )
    return _parser


def parse(source: str) -> Program:
    """Parse Lumon source code into an AST Program node."""
    source = _preprocess(source)
    # Ensure source ends with newline for the indenter
    if not source.endswith("\n"):
        source += "\n"
    try:
        parser = _get_parser()
        tree = parser.parse(source)
        result = LumonTransformer().transform(tree)
        if isinstance(result, Program):
            return result
        return Program((result,))
    except Exception as e:
        raise LumonError(f"Parse error: {e}") from e
