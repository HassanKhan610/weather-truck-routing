import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def test_pyproject_and_requirements_list_the_same_pins():
    requirements = {
        line.strip()
        for line in (BACKEND / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    pyproject = (BACKEND / "pyproject.toml").read_text()
    block = re.search(r"^dependencies = \[(.*?)^\]", pyproject, re.S | re.M).group(1)
    assert set(re.findall(r'"([^"]+)"', block)) == requirements
