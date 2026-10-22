## Agent skills

### Issue tracker

GitHub Issues on `hoangvantuan/VideoLingo`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Sensitive files

Do not read, print, grep, or copy these files. They hold real credentials:

- `config.yaml`: the local config, ignored by git. It holds API keys such as `api.key`, `whisper.*_api_key`, and `*_tts.api_key`.
  - To learn the structure or the default values of the config, read `config.example.yaml`.
  - To read a single setting that is not a secret, use `load_key('...')` from `core/utils/config_utils.py`.
  - Never print or log the value of a key whose name contains `key`, `token`, or `secret`.
- `config.backup.yaml`, `.env`, `.env.*`, `.private-llm.*`, and `docs/private-*.md`.
- The cookies file at the path set in `youtube.cookies_path`.
- Environment variables that hold keys, such as `SONIOX_API_KEY`. Do not run `env` or `printenv` without a filter.

Never put real keys in tracked files: `config.example.yaml`, tests, docs, commit messages, or issues. When a new config key is added, add it to `config.example.yaml` with a placeholder value.
