from __future__ import annotations

import ast
import math
import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple, Union


Number = Union[int, float]
Vector = List[Union[Number, bool]]
Value = Union[Number, bool, Vector]


@dataclass
class Statement:
    kind: str
    name: Optional[str] = None
    expr: Optional[str] = None
    count: int = 0
    body: Optional[List["Statement"]] = None
    else_body: Optional[List["Statement"]] = None
    dtype: str = "float"
    ms: int = 0


@dataclass
class CStarProgram:
    statements: List[Statement]


def _strip_comments(line: str) -> str:
    idx = line.find("#")
    if idx >= 0:
        line = line[:idx]
    return line.strip()


def parse_cstar(path: str) -> CStarProgram:
    with open(path, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    lines: List[str] = []
    for raw in raw_lines:
        line = _strip_comments(raw)
        if not line:
            continue
        # Accept common C formatting style: "} else {"
        if line == "} else {":
            lines.append("}")
            lines.append("else {")
            continue
        lines.append(line)

    statements, idx = _parse_block(lines, 0)
    if idx != len(lines):
        raise ValueError(f"Unexpected trailing input at line {idx + 1}")
    return CStarProgram(statements)


def _parse_block_header(line: str, keyword: str) -> str:
    # Expected: "<keyword> (<expr>) {"
    prefix = f"{keyword} "
    if not (line.startswith(prefix) and line.endswith("{")):
        raise ValueError(f"Use '{keyword} (<expr>) {{' on a single line.")
    middle = line[len(prefix) : -1].strip()
    if not (middle.startswith("(") and middle.endswith(")")):
        raise ValueError(f"Use '{keyword} (<expr>) {{' with parentheses.")
    return middle[1:-1].strip()


def _parse_block(lines: List[str], idx: int) -> Tuple[List[Statement], int]:
    stmts: List[Statement] = []
    while idx < len(lines):
        line = lines[idx]
        if line == "}":
            return stmts, idx + 1

        if line.startswith("pvar ") or line.startswith("float ") or line.startswith("int ") or line.startswith("bool "):
            # pvar float x;
            is_pvar = line.startswith("pvar ")
            body = line[5:].strip() if is_pvar else line.strip()
            if not body.endswith(";"):
                raise ValueError(f"Missing ';' in declaration: {line}")
            body = body[:-1].strip()
            parts = body.split()
            if len(parts) != 2:
                raise ValueError(f"Invalid declaration: {line}")
            dtype, name = parts
            kind = "pvar" if is_pvar else "scalar_decl"
            stmts.append(Statement(kind=kind, name=name, dtype=dtype))
            idx += 1
            continue

        if line.startswith("forall"):
            if line != "forall {":
                raise ValueError("Use 'forall {' on a single line.")
            body, idx = _parse_block(lines, idx + 1)
            stmts.append(Statement(kind="forall", body=body))
            continue

        if line.startswith("where "):
            expr = _parse_block_header(line, "where")
            body, idx = _parse_block(lines, idx + 1)
            stmts.append(Statement(kind="where", expr=expr, body=body))
            continue

        if line.startswith("if "):
            expr = _parse_block_header(line, "if")
            body, idx = _parse_block(lines, idx + 1)
            else_body: Optional[List[Statement]] = None
            if idx < len(lines) and lines[idx] == "else {":
                else_body, idx = _parse_block(lines, idx + 1)
            stmts.append(Statement(kind="if", expr=expr, body=body, else_body=else_body))
            continue

        if line.startswith("while "):
            expr = _parse_block_header(line, "while")
            body, idx = _parse_block(lines, idx + 1)
            stmts.append(Statement(kind="while", expr=expr, body=body))
            continue

        if line.startswith("repeat "):
            # repeat 100 {
            if not line.endswith("{"):
                raise ValueError("Use 'repeat <count> {'")
            middle = line[len("repeat ") : -1].strip()
            count = int(middle)
            body, idx = _parse_block(lines, idx + 1)
            stmts.append(Statement(kind="repeat", count=count, body=body))
            continue

        if line.startswith("sleep "):
            # sleep 40;
            body = line[len("sleep ") :].strip()
            if not body.endswith(";"):
                raise ValueError(f"Missing ';' in sleep: {line}")
            ms = int(body[:-1].strip())
            stmts.append(Statement(kind="sleep", ms=ms))
            idx += 1
            continue

        if line.startswith("led"):
            # led = expr;
            if line.startswith("led("):
                if not line.endswith(");"):
                    raise ValueError(f"Invalid led() statement: {line}")
                expr = line[len("led(") : -2].strip()
            else:
                if "=" not in line or not line.endswith(";"):
                    raise ValueError(f"Invalid led statement: {line}")
                expr = line.split("=", 1)[1].strip()[:-1].strip()
            stmts.append(Statement(kind="led", expr=expr))
            idx += 1
            continue

        if "=" in line:
            if not line.endswith(";"):
                raise ValueError(f"Missing ';' in assignment: {line}")
            left, right = line[:-1].split("=", 1)
            name = left.strip()
            expr = right.strip()
            stmts.append(Statement(kind="assign", name=name, expr=expr))
            idx += 1
            continue

        raise ValueError(f"Cannot parse line: {line}")
    return stmts, idx


class CStarRuntime:
    def __init__(
        self,
        processor_count: int,
        processors_per_chip: int = 16,
        chip_cols: int = 64,
        chip_rows: int = 32,
        news_wrap: bool = True,
    ):
        self.processor_count = processor_count
        self.processors_per_chip = processors_per_chip
        self.chip_cols = chip_cols
        self.chip_rows = chip_rows
        self.news_wrap = news_wrap
        self.chips_per_side = chip_cols * chip_rows
        self.step = 0
        self.vars: Dict[str, Vector] = {}
        self.scalars: Dict[str, Value] = {}
        self.var_types: Dict[str, str] = {}
        self.active_mask: List[bool] = [True] * processor_count
        self._builtins: Dict[str, Callable[..., Value]] = {
            "rand": self._rand,
            "index": self._index,
            "chip": self._chip,
            "time": self._time,
            "sin": self._sin,
            "cos": self._cos,
            "abs": self._abs,
            "news_n": self._news_n,
            "news_s": self._news_s,
            "news_e": self._news_e,
            "news_w": self._news_w,
        }

    def execute(
        self,
        program: CStarProgram,
        on_led: Callable[[Optional[List[bool]], int], None],
    ) -> None:
        self._run_block(program.statements, on_led)

    def _run_block(
        self,
        statements: List[Statement],
        on_led: Callable[[Optional[List[bool]], int], None],
    ) -> None:
        for stmt in statements:
            kind = stmt.kind
            if kind == "pvar":
                self.vars[stmt.name or ""] = [0.0] * self.processor_count
                self.var_types[stmt.name or ""] = "pvar"
            elif kind == "scalar_decl":
                self.scalars[stmt.name or ""] = 0.0
                self.var_types[stmt.name or ""] = "scalar"
            elif kind == "assign":
                value = self._eval_expr(stmt.expr or "")
                name = stmt.name or ""
                vtype = self.var_types.get(name)
                if vtype == "scalar":
                    self.scalars[name] = self._to_scalar(value)
                elif vtype == "pvar":
                    self._assign_pvar(name, value)
                else:
                    # Auto-create: scalar for scalar value, pvar for vector value.
                    if isinstance(value, list):
                        self.vars[name] = self._to_vector(value)
                        self.var_types[name] = "pvar"
                    else:
                        self.scalars[name] = value
                        self.var_types[name] = "scalar"
                self.step += 1
            elif kind == "forall":
                old_mask = self.active_mask
                self.active_mask = [True] * self.processor_count
                self._run_block(stmt.body or [], on_led)
                self.active_mask = old_mask
            elif kind == "where":
                cond = self._to_bool_vector(self._eval_expr(stmt.expr or ""))
                old_mask = self.active_mask
                self.active_mask = [old_mask[i] and cond[i] for i in range(self.processor_count)]
                self._run_block(stmt.body or [], on_led)
                self.active_mask = old_mask
            elif kind == "if":
                cond = self._eval_expr(stmt.expr or "")
                cond_val = self._condition_to_bool(cond)
                if cond_val:
                    self._run_block(stmt.body or [], on_led)
                else:
                    self._run_block(stmt.else_body or [], on_led)
            elif kind == "while":
                guard = 0
                while self._condition_to_bool(self._eval_expr(stmt.expr or "")):
                    self._run_block(stmt.body or [], on_led)
                    guard += 1
                    if guard > 100000:
                        raise RuntimeError("while guard triggered (possible endless loop)")
            elif kind == "repeat":
                for _ in range(stmt.count):
                    self._run_block(stmt.body or [], on_led)
            elif kind == "led":
                value = self._eval_expr(stmt.expr or "")
                vec = self._to_bool_vector(value)
                vec = [vec[i] and self.active_mask[i] for i in range(self.processor_count)]
                on_led(vec, 0)
                self.step += 1
            elif kind == "sleep":
                on_led(None, stmt.ms)
            else:
                raise ValueError(f"Unsupported statement kind: {kind}")

    def _eval_expr(self, expr: str) -> Value:
        node = ast.parse(expr, mode="eval").body
        return self._eval_node(node)

    def _eval_node(self, node: ast.AST) -> Value:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in self.vars:
                return self.vars[node.id]
            if node.id in self.scalars:
                return self.scalars[node.id]
            if node.id in ("true", "True"):
                return True
            if node.id in ("false", "False"):
                return False
            raise ValueError(f"Unknown identifier: {node.id}")
        if isinstance(node, ast.UnaryOp):
            val = self._eval_node(node.operand)
            if isinstance(node.op, ast.USub):
                return _elementwise_unary(val, lambda x: -x)
            if isinstance(node.op, ast.Not):
                return _elementwise_unary(val, lambda x: not bool(x))
            raise ValueError("Unsupported unary operator")
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op = node.op
            if isinstance(op, ast.Add):
                return _elementwise_binary(left, right, lambda a, b: a + b)
            if isinstance(op, ast.Sub):
                return _elementwise_binary(left, right, lambda a, b: a - b)
            if isinstance(op, ast.Mult):
                return _elementwise_binary(left, right, lambda a, b: a * b)
            if isinstance(op, ast.Div):
                return _elementwise_binary(left, right, lambda a, b: a / b)
            if isinstance(op, ast.Mod):
                return _elementwise_binary(left, right, lambda a, b: a % b)
            if isinstance(op, ast.FloorDiv):
                return _elementwise_binary(left, right, lambda a, b: a // b)
            raise ValueError("Unsupported binary operator")
        if isinstance(node, ast.BoolOp):
            values = [self._eval_node(v) for v in node.values]
            if not values:
                return False
            out = values[0]
            for v in values[1:]:
                if isinstance(node.op, ast.And):
                    out = _elementwise_binary(out, v, lambda a, b: bool(a) and bool(b))
                elif isinstance(node.op, ast.Or):
                    out = _elementwise_binary(out, v, lambda a, b: bool(a) or bool(b))
                else:
                    raise ValueError("Unsupported boolean operator")
            return out
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise ValueError("Only single comparisons are supported")
            left = self._eval_node(node.left)
            right = self._eval_node(node.comparators[0])
            op = node.ops[0]
            if isinstance(op, ast.Gt):
                return _elementwise_binary(left, right, lambda a, b: a > b)
            if isinstance(op, ast.GtE):
                return _elementwise_binary(left, right, lambda a, b: a >= b)
            if isinstance(op, ast.Lt):
                return _elementwise_binary(left, right, lambda a, b: a < b)
            if isinstance(op, ast.LtE):
                return _elementwise_binary(left, right, lambda a, b: a <= b)
            if isinstance(op, ast.Eq):
                return _elementwise_binary(left, right, lambda a, b: a == b)
            if isinstance(op, ast.NotEq):
                return _elementwise_binary(left, right, lambda a, b: a != b)
            raise ValueError("Unsupported comparison")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls are supported")
            fn_name = node.func.id
            fn = self._builtins.get(fn_name)
            if fn is None:
                raise ValueError(f"Unknown function: {fn_name}")
            args = [self._eval_node(a) for a in node.args]
            return fn(*args)
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    def _to_vector(self, value: Value) -> Vector:
        if isinstance(value, list):
            if len(value) != self.processor_count:
                raise ValueError("Vector length mismatch")
            return value
        return [value] * self.processor_count

    def _to_bool_vector(self, value: Value) -> List[bool]:
        vec = self._to_vector(value)
        return [bool(v) for v in vec]

    def _to_scalar(self, value: Value) -> Value:
        if isinstance(value, list):
            for i, active in enumerate(self.active_mask):
                if active:
                    return value[i]
            return value[0] if value else 0
        return value

    def _assign_pvar(self, name: str, value: Value) -> None:
        vec = self._to_vector(value)
        base = self.vars.get(name, [0.0] * self.processor_count)
        out = base[:]
        for i, active in enumerate(self.active_mask):
            if active:
                out[i] = vec[i]
        self.vars[name] = out

    def _condition_to_bool(self, value: Value) -> bool:
        if isinstance(value, list):
            return any(bool(value[i]) and self.active_mask[i] for i in range(self.processor_count))
        return bool(value)

    def _rand(self) -> Vector:
        return [random.random() for _ in range(self.processor_count)]

    def _index(self) -> Vector:
        return list(range(self.processor_count))

    def _chip(self) -> Vector:
        return [i // self.processors_per_chip for i in range(self.processor_count)]

    def _time(self) -> Number:
        return self.step

    def _sin(self, value: Value) -> Value:
        return _elementwise_unary(value, math.sin)

    def _cos(self, value: Value) -> Value:
        return _elementwise_unary(value, math.cos)

    def _abs(self, value: Value) -> Value:
        return _elementwise_unary(value, abs)

    def _news_n(self, value: Value) -> Value:
        return self._news_shift(value, d_row=-1, d_col=0)

    def _news_s(self, value: Value) -> Value:
        return self._news_shift(value, d_row=1, d_col=0)

    def _news_e(self, value: Value) -> Value:
        return self._news_shift(value, d_row=0, d_col=1)

    def _news_w(self, value: Value) -> Value:
        return self._news_shift(value, d_row=0, d_col=-1)

    def _news_shift(self, value: Value, d_row: int, d_col: int) -> Value:
        src = self._to_vector(value)
        out: Vector = [0.0] * self.processor_count

        ppc = self.processors_per_chip
        cols = self.chip_cols
        rows = self.chip_rows
        cps = self.chips_per_side

        for idx in range(self.processor_count):
            chip = idx // ppc
            lane = idx % ppc

            side = chip // cps
            local_chip = chip % cps
            row = local_chip // cols
            col = local_chip % cols

            n_row = row + d_row
            n_col = col + d_col
            if self.news_wrap:
                n_row %= rows
                n_col %= cols
            else:
                if n_row < 0 or n_row >= rows or n_col < 0 or n_col >= cols:
                    out[idx] = 0.0
                    continue

            n_local_chip = n_row * cols + n_col
            n_chip = side * cps + n_local_chip
            src_idx = n_chip * ppc + lane
            out[idx] = src[src_idx]
        return out


def _elementwise_unary(value: Value, fn: Callable[[Number], Value]) -> Value:
    if isinstance(value, list):
        return [fn(v) for v in value]
    return fn(value)


def _elementwise_binary(left: Value, right: Value, fn: Callable[[Number, Number], Value]) -> Value:
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            raise ValueError("Vector length mismatch")
        return [fn(a, b) for a, b in zip(left, right)]
    if isinstance(left, list):
        return [fn(a, right) for a in left]
    if isinstance(right, list):
        return [fn(left, b) for b in right]
    return fn(left, right)
