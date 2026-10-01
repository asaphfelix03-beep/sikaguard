"""The opening example of both READMEs must match the real output of the bundled model."""

import re
from pathlib import Path

import pytest

from sikaguard.analyzer import Analyzer
from sikaguard.model import load_model

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("readme", ["README.md", "README.fr.md"])
def test_readme_example_matches_model_output(readme: str) -> None:
    text = (ROOT / readme).read_text(encoding="utf-8")
    block = text.split("```python", 1)[1].split("```", 1)[0]
    sms = re.search(r'analyze\("(.+?)"\)', block)
    assert sms is not None
    expected_reasons = [line[2:] for line in block.splitlines() if line.startswith("- ")]
    expected_verdict = re.search(r"\('(\w+)', '(\w+)'\)", block)
    assert expected_verdict is not None

    result = Analyzer(model=load_model()).analyze(sms.group(1))
    assert (result.verdict, result.category) == expected_verdict.groups()
    assert [r.message for r in result.reasons] == expected_reasons
