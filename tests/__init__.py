from pathlib import Path

# Custom (#22): the config.yaml template that tests read and copy, so they do not depend on the operator's
# config.yaml in the repo. Refresh: git show HEAD:config.yaml > tests/fixtures/config.yaml
TEMPLATE_CONFIG = Path(__file__).resolve().parent / "fixtures" / "config.yaml"
