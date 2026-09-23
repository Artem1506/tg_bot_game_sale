---
name: bot-architecture
description: >-
  Explains and extends Epic Free Games Bot architecture (aiogram 3, Epic API,
  Fab curl parser, publisher, scheduler, history). Use when debugging posts,
  adding commands, changing EGS/FAB clients, MarkdownV2, or explaining how the
  bot works.
---

# Архитектура бота

## Когда читать reference

Сначала этот файл. Подробный разбор модулей — в [reference.md](reference.md).

## Карта модулей

| Задача | Файл |
|---|---|
| Токены, чаты, админы | `src/config.py` → `settings` |
| Демон / polling | `src/main.py` |
| Разовая проверка | `src/run_once.py` |
| Игры EGS | `src/api/epic_client.py` |
| Ассеты Fab | `src/api/fab_client.py` |
| Тексты и отправка | `src/bot/publisher.py` |
| Команды | `src/bot/handlers.py` |
| Расписание | `src/bot/scheduler.py` |
| Дубликаты | `src/bot/history.py` → `history.json` |
| Архив чатов | `src/bot/channels.py` → `channels.json` |
| Логи входящих + автозахват | `src/bot/middlewares.py` |

## Правила при изменениях

1. Новые тексты постов и `parse_mode` — только в `publisher.py`.
2. Рассылка идёт по `settings.channel_ids` (`.env`), не по всему `channels.json`.
3. Фоновые проверки EGS и Fab держать в отдельных `try/except`.
4. Fab: только `curl`, не `aiohttp`/`requests`.
5. EGS: не убирать `country=US` + `locale=ru`.
6. MarkdownV2: пользовательский текст через `escape_markdown`. В Python-строке слэш — `\\`.
7. `/check` и `/check_fab` без `channel` не пишут в каналы и не обязаны обходить историю.

## Отладка

1. Смотреть `bot_activity.log` (UTF-8) и `logs/app.log`.
2. Превью: `/check` и `/check_fab` в ЛС.
3. Список чатов: `/dev_channels` (ID разработчика `1205125640`).
