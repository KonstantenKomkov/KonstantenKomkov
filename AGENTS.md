# Repository Guidelines

## Product scope

The source of truth for version 1 is `development_v1.md`.

Implement only the features listed there:

- commit activity for 7, 30, and 365 days;
- added and deleted code lines for the same periods;
- programming-language and technology usage;
- GitHub-profile README rendering and period selection;
- scheduled aggregation across repositories available to the configured GitHub account, including private repositories;
- quality and security controls required to publish those aggregates safely.

Do not add unrelated profile sections, social statistics, badges, time tracking, AI usage, editor usage, operating-system usage, or other features from reference profiles.

## Architecture

- Keep the application as a small CLI without a web server or database unless a backlog change explicitly requires them.
- Follow Clean Architecture dependency direction: `domain` must not depend on application or infrastructure; `application` may depend on domain and ports; adapters implement ports; entrypoints assemble dependencies.
- Keep GitHub API, Git commands, filesystem access, clocks, and SVG rendering behind explicit ports where doing so enables deterministic tests.
- Prefer simple domain values and use cases over framework-specific abstractions.
- Generated SVG and README output must be deterministic for the same input and clock.
- Keep third-party dependencies to the minimum necessary and pin their versions reproducibly.

## Activity semantics

- Count only commits authored by identities explicitly configured for the profile owner.
- Deduplicate commits globally by SHA across repositories, forks, and branches.
- Aggregate calendar days in the configured timezone; default to `Europe/Moscow`.
- Treat code-line activity as added and deleted source lines from the selected commits.
- Exclude binary, generated, vendored, lock, and documentation files from code-line metrics.
- Use at most the latest 365 days of history for version 1.
- Language statistics should follow GitHub Linguist semantics.
- Detect technologies only through an explicit allowlist of known manifest files and technology names.

## Privacy and security

- Never commit credentials, tokens, private keys, private author emails, or real secrets used in tests.
- Read credentials only from environment variables or GitHub Actions Secrets.
- Use a read-only credential for private repository collection and the workflow `GITHUB_TOKEN` only for writing generated files to the profile repository.
- Never place credentials in clone URLs, command arguments that are logged, exceptions, generated files, caches, or artifacts.
- Public output and public logs must not contain private repository names or URLs, file paths, commit messages, author emails, dependency names unique to a private project, or source code.
- Emit only aggregate counts and allowlisted public language or technology names.
- Do not persist private repository clones in caches or upload them as artifacts.
- Treat missing access, partial pagination, and failed repository collection as errors; do not silently publish incomplete statistics.
- Escape all data written to Markdown or SVG and validate generated output for private-data leakage.
- Pin third-party GitHub Actions by full commit SHA.
- A release is blocked by detected secrets or known high/critical dependency vulnerabilities.

## Testing and verification

- Add or update tests with every behavioral change.
- Unit-test date boundaries, timezones, author matching, SHA deduplication, exclusions, aggregation, and rendering.
- Use temporary local Git repositories for integration tests; tests must not require access to real GitHub repositories or credentials.
- Keep snapshot/golden tests for generated SVG where appropriate.
- Include a negative privacy test proving that private fixture names, URLs, paths, emails, and commit messages do not occur in public output.
- Before completing a task, run all available formatting, linting, type-checking, test, dependency, and secret checks relevant to the changed code.
- Do not claim that a check passed if it was not run; report unavailable checks explicitly.

## Backlog workflow

- Work on one top-level task from `development_v1.md` at a time unless the user explicitly changes the scope.
- Before implementation, identify the task's acceptance criterion and the smallest complete change that satisfies it.
- After implementation, review the complete diff for correctness, architecture, privacy, and security; fix all findings before marking the task complete.
- Move a completed top-level task from `development_v1.md` to `completed_v1.md`, preserving its checklist and acceptance criterion.
- Keep each completed top-level task in a separate commit and do not mix unrelated changes.
- Do not mark a task complete while required tests fail or required work remains.

## Repository conventions

- Write code identifiers and code comments in English.
- Keep user-facing documentation in Russian unless the existing document establishes another language.
- Do not edit generated files manually once a generator exists.
- Preserve user changes and avoid unrelated rewrites.
- Update this file when implementation tooling introduces canonical local commands that future agents must run.

## Canonical local commands

- `make bootstrap` — создать `.venv` и установить закреплённые инструменты разработки;
- `make format` — отформатировать код и применить безопасные lint-исправления;
- `make format-check` — проверить форматирование без изменения файлов;
- `make lint` — запустить статический анализ Ruff;
- `make typecheck` — запустить строгую проверку типов mypy;
- `make test` — запустить тесты pytest;
- `make check` — выполнить все обязательные локальные проверки;
- `make run` — выполнить пустой локальный CLI-сценарий.
