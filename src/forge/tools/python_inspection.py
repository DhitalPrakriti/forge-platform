"""Bounded syntax/structure inspection. Never imports or executes supplied code."""

import ast

from pydantic import BaseModel, ConfigDict, Field


class PythonInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: str = Field(min_length=1, max_length=12000)


class PythonOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    syntax_valid: bool
    syntax_error: str | None
    functions: list[str]
    classes: list[str]
    imports: list[str]
    division_lines: list[int]
    executed: bool = False


def inspect_python(code: str) -> dict:
    result = dict(
        syntax_valid=False,
        syntax_error=None,
        functions=[],
        classes=[],
        imports=[],
        division_lines=[],
        executed=False,
    )
    try:
        tree = ast.parse(code)
        result["syntax_valid"] = True
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result["functions"].append(node.name)
            elif isinstance(node, ast.ClassDef):
                result["classes"].append(node.name)
            elif isinstance(node, ast.Import):
                result["imports"].extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                result["imports"].append(node.module or ".")
            elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv)):
                result["division_lines"].append(node.lineno)
    except SyntaxError as exc:
        result["syntax_error"] = f"{exc.msg} at line {exc.lineno}"
    except (ValueError, RecursionError):
        result["syntax_error"] = "Code cannot be parsed within inspection limits."
    return result
