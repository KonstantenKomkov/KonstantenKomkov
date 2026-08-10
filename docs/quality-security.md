# Проверки качества и безопасности

Проект требует Python 3.10 или новее. Минимальная версия повышена с 3.9, потому
что исправленные версии build- и test-инструментов с закрытыми high-severity
уязвимостями больше не поддерживают Python 3.9.

Локальная подготовка и полный набор воспроизводимых проверок:

```shell
make bootstrap SYSTEM_PYTHON=python3.12
make check
```

`make check` запускает Ruff formatter, Ruff linter, строгий mypy, все unit-,
integration- и snapshot-тесты, затем `pip check`. Integration-тест создаёт только
временный локальный Git-репозиторий и не использует сеть или реальные credentials.

## CI

Workflow `ci.yml` выполняет quality matrix на минимальном Python 3.10 и актуальном
Python 3.14. Отдельный blocking job запускает `pip-audit` для полного закреплённого
`requirements-dev.lock`, куда включён build backend. Сам сканер и все его
зависимости изолированно закреплены в `requirements-audit.lock` и также проходят
аудит. Любой известный advisory приводит к ошибке, то есть политика строже
обязательного запрета high/critical.

Gitleaks получает checkout с полной историей и запускается с закреплённой версией
движка. Комментарии, job summary и загрузка SARIF artifact отключены, чтобы
результат возможной находки не создавал дополнительную публичную копию. Для
репозитория личного аккаунта license secret не нужен; при переносе в организацию
нужно создать `GITLEAKS_LICENSE` согласно условиям Gitleaks Action.

Workflow `codeql.yml` запускает расширенный Python CodeQL analysis на push, pull
request, version tag, вручную и еженедельно. Все внешние Actions во всех workflow
закреплены полными commit SHA; статический тест отклоняет tag- и branch-ссылки.

## Release gate

Job `Release gate` завершается успешно только после quality matrix, dependency
audit и полноисторического secret scan. В ruleset основной ветки и version tags
следует запретить bypass и сделать обязательными checks `Release gate` и
`CodeQL / Analyze Python`. Выпускать версию можно только из commit, для которого
оба checks завершились успешно.
