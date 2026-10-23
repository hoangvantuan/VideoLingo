## Agent skills

### Issue tracker

GitHub Issues on `hoangvantuan/VideoLingo`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Sensitive files

`config.yaml` is tracked by git (#22). It is not a sensitive file, but it must never hold a real key: every key field is `${VAR}`, `${VAR:-}`, empty, or a `YOUR_...` placeholder, and the value lives in `.env`. `tests/test_tracked_config.py` fails otherwise.

- Read `config.yaml` to learn the structure or the default values of the config. To read a single setting from code, use `load_key('...')` from `core/utils/config_utils.py`.
- Never print or log the resolved value of a key whose name contains `key`, `token`, or `secret`.

Do not read, print, grep, or copy these files. They hold real credentials:

- `.env`, `.env.*` (except `.env.example`, which lists the variable names with empty values), `config.backup.yaml` (written by `scripts/move_keys_to_env.py`), `.private-llm.*`, and `docs/private-*.md`.
- Google service account key files such as `vertex-sa.json` or the file set in `GOOGLE_APPLICATION_CREDENTIALS`.
- The cookies file at the path set in `youtube.cookies_path`.
- Environment variables that hold keys, such as `SONIOX_API_KEY`. Do not run `env` or `printenv` without a filter.

Never put real keys in tracked files: `config.yaml`, tests, docs, commit messages, or issues. When a new key is added to the config, write it in `config.yaml` as `'${VAR_NAME:-}'` and add `VAR_NAME=` to `.env.example`. Other new config keys go in `config.yaml` with their default value.
