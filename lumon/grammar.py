"""Lark grammar definition for the Lumon language."""

GRAMMAR = r"""
start: _NL* (statement (_NL+ statement)*)? _NL*

// === Statements ===
?statement: define_block
          | implement_block
          | let_binding
          | return_stmt
          | if_stmt
          | match_expr
          | expression

let_binding: "let" IDENT "=" expression
return_stmt: "return" expression

// === Define / Implement ===
define_block: "define" namespace_path _NL _INDENT description _NL takes_clause? _NL? returns_clause _NL _DEDENT
description: ESCAPED_STRING
takes_clause: "takes:" _NL _INDENT param_def+ _DEDENT
param_def: IDENT ":" type_expr ESCAPED_STRING ("=" expression)? _NL
returns_clause: "returns:" type_expr ESCAPED_STRING

implement_block: "implement" namespace_path _NL _INDENT impl_body _DEDENT
impl_body: (impl_statement _NL)* impl_statement?
?impl_statement: let_binding
               | return_stmt
               | if_stmt
               | match_expr
               | expression

// === Expressions (precedence climbing) ===
?expression: lambda_expr
           | pipe_expr

?pipe_expr: nil_coalesce_expr (PIPE pipe_target)*
?pipe_target: function_call
            | namespace_ref
            | IDENT -> var_ref_target
            | lambda_expr

?nil_coalesce_expr: or_expr (DBLQUEST or_expr)*

?or_expr: and_expr ("or" and_expr)*
?and_expr: not_expr ("and" not_expr)*
?not_expr: "not" not_expr -> not_op
         | comparison_expr
?comparison_expr: add_expr ((LTE | GTE | EQEQ | NEQ | LT | GT) add_expr)*
?add_expr: mul_expr (PLUS mul_expr | MINUS mul_expr)*
?mul_expr: unary_expr (MUL_OP unary_expr)*
?unary_expr: MINUS unary_expr -> neg_op
           | postfix_expr

?postfix_expr: primary postfix_access*
?postfix_access: "." IDENT -> dot_access
               | "[" expression "]" -> index_access

// === Primary expressions ===
?primary: "(" expression ")"
        | inline_if_expr
        | match_expr
        | with_expr
        | ask_expr
        | spawn_expr
        | "async" expression -> async_expr
        | "await_all" expression -> await_all_expr
        | "await" expression -> await_expr
        | function_call
        | tag_literal
        | list_literal
        | map_literal
        | NUMBER -> number_lit
        | ESCAPED_STRING -> simple_string
        | "true" -> true_lit
        | "false" -> false_lit
        | "none" -> none_lit
        | IDENT -> var_ref

// === Function calls (for pipe targets and define/implement) ===
function_call: namespace_path "(" arguments? ")"
             | IDENT "(" arguments? ")" -> local_call
arguments: expression ("," expression)*
namespace_path: IDENT ("." (IDENT | FN_KW))+
namespace_ref: namespace_path

// === Literals ===
tag_literal: ":" IDENT ("(" expression ")")?
list_literal: "[" (expression ("," expression)*)? "]"
map_literal: "{" (map_entry ("," map_entry)*)? "}"
?map_entry: "..." expression -> spread_entry
          | IDENT ":" expression -> kv_entry

// === Control flow ===
inline_if_expr: "if" expression expression "else" expression

if_stmt: "if" expression _NL _INDENT block _DEDENT _NL? else_clause?
else_clause: "else" _NL _INDENT block _DEDENT

block: (block_statement _NL)* block_statement?
?block_statement: let_binding
                | return_stmt
                | if_stmt
                | match_expr
                | expression

// === Match ===
match_expr: "match" expression _NL _INDENT match_arm (_NL match_arm)* _NL? _DEDENT
match_arm: pattern guard? ARROW arm_body
guard: "if" expression
?arm_body: _NL _INDENT block _DEDENT -> arm_block
         | return_stmt -> arm_inline
         | expression -> arm_inline

// === Patterns ===
?pattern: tag_pattern
        | map_pattern
        | list_pattern
        | NUMBER -> lit_pattern_num
        | ESCAPED_STRING -> lit_pattern_str
        | "true" -> lit_pattern_true
        | "false" -> lit_pattern_false
        | "none" -> lit_pattern_none
        | "_" -> wildcard_pattern
        | IDENT -> bind_pattern

tag_pattern: ":" IDENT ("(" pattern ")")?
map_pattern: "{" (map_pattern_entry ("," map_pattern_entry)*)? "}"
map_pattern_entry: IDENT ":" pattern
list_pattern: "[" (list_pattern_element ("," list_pattern_element)*)? "]"
?list_pattern_element: "..." IDENT -> rest_pattern
                     | pattern

// === Lambda ===
lambda_expr: FN_KW "(" params? ")" ARROW lambda_body
params: IDENT ("," IDENT)*
?lambda_body: _NL _INDENT block _DEDENT -> lambda_block
            | expression -> lambda_inline

// === With / Then / Else ===
with_expr: "with" _NL _INDENT with_binding+ _DEDENT _NL? "then" _NL _INDENT block _DEDENT _NL? "else" _NL _INDENT block _DEDENT
with_binding: IDENT "=" expression _NL

// === Ask / Spawn ===
ask_expr: "ask" _NL _INDENT ask_body _DEDENT
ask_body: ESCAPED_STRING _NL ask_fields
ask_fields: (ask_context _NL)? (ask_expects _NL)?
ask_context: "context:" expression
ask_expects: "expects:" type_expr

spawn_expr: "spawn" _NL _INDENT spawn_body _DEDENT
spawn_body: ESCAPED_STRING _NL spawn_fields
spawn_fields: (spawn_context _NL)? (spawn_fork _NL)? (spawn_expects _NL)?
spawn_context: "context:" expression
spawn_fork: "fork:" expression
spawn_expects: "expects:" type_expr

// === Type expressions ===
?type_expr: type_union
?type_union: type_single ("|" type_single)* -> type_union_node
?type_single: IDENT LT type_expr GT -> type_parameterized
            | struct_type
            | tag_type
            | fn_type
            | IDENT -> type_name
struct_type: "{" IDENT ":" type_expr ("," IDENT ":" type_expr)* "}"
tag_type: ":" IDENT ("(" type_expr ")")?
fn_type: FN_KW "(" (type_expr ("," type_expr)*)? ")" ARROW type_expr

// === Operators (named terminals to avoid conflicts) ===
LT: "<"
GT: ">"
LTE: "<="
GTE: ">="
EQEQ: "=="
NEQ: "!="
MUL_OP: "*" | "/" | "%"
PLUS: "+"
MINUS: "-"
PIPE: "|>"
DBLQUEST: "??"
ARROW: "->"
FN_KW: "fn"

// === Terminals ===
COMMENT: /--[^\n]*/
%ignore COMMENT
%ignore /[ \t]+/

// These are declared for the Indenter
%declare _INDENT _DEDENT
_NL: /(\r?\n[\t ]*)+/

IDENT: /(?!(?:let|define|implement|takes|returns|return|match|if|else|with|then|ask|spawn|fork|context|expects|async|await|await_all|assert|true|false|none|and|or|not)\b)[a-zA-Z_][a-zA-Z0-9_]*/
NUMBER: /\d+(\.\d+)?/
ESCAPED_STRING: "\"" /([^\"\\]|\\[\\\"nrt]|\\\([^)]*\))*/ "\""
"""
