from forge.tools.builtins import DEFINITIONS
from forge.tools.python_inspection import inspect_python


def test_inspection_reports_structure_without_execution():
    code = 'import os\nraise RuntimeError("must never run")\ndef divide(a,b):\n    return a / b'
    result = inspect_python(code)
    assert result["syntax_valid"]
    assert result["functions"] == ["divide"]
    assert result["imports"] == ["os"]
    assert result["division_lines"] == [4]
    assert result["executed"] is False
    DEFINITIONS["inspect_python"].output_model.model_validate(result)


def test_invalid_python_is_useful_tool_output():
    result = inspect_python("def broken(:")
    assert not result["syntax_valid"]
    assert "line 1" in result["syntax_error"]
