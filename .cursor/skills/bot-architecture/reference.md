# Разбор модулей Epic Free Games Bot

## Структура

```
src/
├── api/epic_client.py    # EGS freeGamesPromotions
├── api/fab_client.py     # Fab.com через curl
├── bot/channels.py       # архив чатов (channels.json)
├── bot/handlers.py       # /start /check /check_fab /help /dev_channels
├── bot/history.py        # history.json
├── bot/middlewares.py    # лог входящих + автозахват чатов
├── bot/publisher.py      # MarkdownV2, альбомы, FAB-посты
├── bot/scheduler.py      # ежедневная проверка
├── config.py             # Settings singleton
├── main.py               # polling-демон
└── run_once.py           # разовый запуск
```

Логи: `logs/app.log` (ротация) и `bot_activity.log` в корне.

## config.py

`Settings` — singleton. Читает `.env` один раз. Импортировать `settings`, не создавать новый экземпляр.

Ключевые поля: `bot_token`, `channel_ids`, `admin_ids`, `check_time`, `epic_api_url`, `history_file`, `channels_file`, `log_file`.

## epic_client.py

Скрытый API акций EGS. Параметры `locale=ru` и `country=US`: список как в США, тексты по возможности на русском (издатели часто режут РФ-аккаунты).

Бесплатная игра: в `promotionalOffers` есть `discountPercentage == 0` и окно дат покрывает сейчас. Retry 3 раза с экспоненциальной паузой.

## fab_client.py

`aiohttp`/`requests` получают 403 от Cloudflare. Рабочий транспорт: `asyncio.create_subprocess_exec("curl", "-s", "-A", user_agent, url)`.

Страница раздач парсится regex. Описания собираются параллельно (`asyncio.gather`) из `<meta name="description">` карточек ассетов.

**Устарело:** поиск через Reddit `/r/unrealengine/search.json`. Не возвращать эту схему.

## history.py и channels.py

- `HistoryManager.is_published(id)` — не публиковать повторно при автопроверке.
- `ChannelsManager` — архив чатов, куда бот когда-либо попадал. Запись на диск только если ID новый или изменились title/type.
- Публикации идут в `settings.channel_ids` из `CHANNEL_ID`.

## middlewares.py

`RequestLoggingMiddleware`:

1. Пишет каждое входящее сообщение в лог.
2. Регистрирует группу/канал в `channels.json`, если событие add было пропущено.

## publisher.py

Несколько игр — `InputMediaPhoto`: подпись только у первого кадра.

`escape_markdown` экранирует `\_*[]()~`>`#+-=|{}.!`.

В f-string/`"` Python сам ест `\`. Чтобы в Telegram ушло `\.`, в коде нужно `\\.`

FAB: `build_fab_post_text` и `publish_fab_assets` — те же функции для `/check_fab` и планировщика.

## scheduler.py

Одна daily-задача `check_and_publish_daily` (время из `CHECK_TIME`). EGS и Fab в отдельных `try/except`.

В `main.py` polling: `allowed_updates=dp.resolve_used_update_types()` — только `message` и `my_chat_member`.

## Режимы

- `main.py` — polling + команды + cron. Для VPS / постоянно включённого ПК.
- `run_once.py` + `run_once.bat` — проверка и выход. Для Task Scheduler.
