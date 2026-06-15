# Project Rules (CLAUDE.md / AGENTS.md)

These are the rules the AI PR reviewer checks every pull request against.
Edit them to match your project. Keep rules concrete and testable.

## Code

- No secrets, API keys, tokens, or passwords committed in code or config.
  Use environment variables instead.
- No hardcoded credentials, connection strings, or absolute local paths
  (e.g. `C:\Users\...`).
- No `print()` debugging left in committed code — use logging.
- Validate and sanitize all external input (HTTP params, file contents,
  CLI args) before use.
- Avoid N+1 queries and loops that call the network/DB inside the loop.

## Tests

- New features or bug fixes must include or update tests.
- A PR that changes behavior with no test changes should be flagged.

## Pull requests

- PR description must explain WHAT changed and WHY.
- Keep PRs focused — unrelated changes should be split out.

## Security

- Never log secrets or full request/response bodies that may contain PII.
- Any new external dependency should be called out in the PR description.