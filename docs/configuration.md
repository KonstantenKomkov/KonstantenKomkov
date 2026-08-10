# Конфигурация

Приложение читает конфигурацию только из переменных окружения. Файл `.env` не
используется, чтобы секретные значения не сохранялись в рабочем дереве.

Обязательные переменные:

- `IT_ACTIVITY_GITHUB_LOGIN` — публичный GitHub login владельца профиля;
- `IT_ACTIVITY_AUTHOR_EMAILS` — разделённые запятыми email, по которым определяется
  авторство коммитов.

Необязательные переменные:

- `IT_ACTIVITY_TIMEZONE` — часовой пояс IANA, по умолчанию `Europe/Moscow`;
- `IT_ACTIVITY_EXCLUDED_REPOSITORIES` — разделённые запятыми полные имена
  репозиториев, которые нужно исключить из сбора.

Проверка конфигурации не выводит email и имена исключённых репозиториев:

```shell
IT_ACTIVITY_GITHUB_LOGIN=octocat \
IT_ACTIVITY_AUTHOR_EMAILS=owner@example.invalid \
.venv/bin/it-activity validate-config
```
