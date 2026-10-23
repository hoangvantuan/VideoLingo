"""Custom (#22): the config.yaml template that tests read and copy, so they do not depend on the operator's
config.yaml in the repo. Refresh after changing config.yaml: git show HEAD:config.yaml > tests/fixtures/config.yaml"""

from pathlib import Path

TEMPLATE_CONFIG = Path(__file__).resolve().parent / "fixtures" / "config.yaml"
