"""Custom (#22): lay the values of your config.yaml over the tracked config.yaml template.

Run it yourself from the repo root, right after merging a version whose config.yaml has new keys:

    python scripts/upgrade_config.py --dry-run   # only prints key paths
    python scripts/upgrade_config.py

The template is `git show HEAD:config.yaml` (or --template FILE). The result has the template's keys, order and
comments, with your value at every key that you have; keys only in your config.yaml are kept and reported.
References such as ${VAR} are copied as written, never resolved. config.yaml is copied to
config.before-upgrade.yaml first (mode 600, ignored by git). Only key paths are printed, never a value.
"""

import argparse
import io
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ruamel.yaml.error import YAMLError  # noqa: E402

from core.utils import config_utils  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP = "config.before-upgrade.yaml"


def overlay(template, config, prefix=""):
    """Put the values of `config` into `template`; returns (added from template, kept from config only)."""
    added = [f"{prefix}{name}" for name in template if name not in config]
    kept = []
    for name, value in config.items():
        path = f"{prefix}{name}"
        if name not in template:
            kept.append(path)
            template[name] = value
        elif isinstance(template[name], dict) and isinstance(value, dict):
            more_added, more_kept = overlay(template[name], value, path + ".")
            added += more_added
            kept += more_kept
        else:
            template[name] = value
    return added, kept


def _load(text, name):
    try:
        return config_utils.yaml.load(text)
    except YAMLError as error:  # the message would quote lines of the file, which may hold a key
        mark = getattr(error, "problem_mark", None)
        line = f" at line {mark.line + 1}" if mark else ""
        raise SystemExit(f"{name} is not valid YAML{line}; fix it and run again.")


def _template_text(path):
    if path:
        with open(path, encoding="utf-8") as file:
            return file.read()
    return subprocess.run(["git", "show", "HEAD:config.yaml"], cwd=ROOT, check=True, capture_output=True,
                          text=True, encoding="utf-8").stdout


def main(argv=None):
    parser = argparse.ArgumentParser(description="Lay config.yaml over the tracked template (see CUSTOM.md).")
    parser.add_argument("--config", default="config.yaml", help="your config.yaml (default: ./config.yaml)")
    parser.add_argument("--template", help="template file (default: git show HEAD:config.yaml)")
    parser.add_argument("--dry-run", action="store_true", help="only print key paths, write nothing")
    args = parser.parse_args(argv)

    with open(args.config, encoding="utf-8") as file:
        original = file.read()
    template = _load(_template_text(args.template), "the template")
    added, kept = overlay(template, _load(original, args.config))
    out = io.StringIO()
    config_utils.yaml.dump(template, out)
    result = out.getvalue()

    for path in added:
        print(f"added from the template: {path}")
    for path in kept:
        print(f"kept, not in the template: {path}")
    if result == original:
        print("Nothing to upgrade.")
        return 0
    if args.dry_run:
        print("Dry run: nothing written.")
        return 0
    backup = os.path.join(os.path.dirname(os.path.abspath(args.config)), BACKUP)
    if os.path.exists(backup):
        print(f"{backup} exists from an earlier run; move it away and run again.")
        return 1
    with open(os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as file:
        file.write(original)  # mode 600: it may still hold a key not yet moved to .env
    with open(args.config, "w", encoding="utf-8") as file:
        file.write(result)
    print(f"Upgraded {args.config}; backup in {backup}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
