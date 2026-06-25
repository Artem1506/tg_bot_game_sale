import logging
from datetime import datetime, timedelta, timezone
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from src.config import settings
from src.api.epic_client import EpicGamesClient
from src.bot.history import HistoryManager
from src.bot.publisher import publish_games

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()
epic_client = EpicGamesClient()

async def check_and_publish_fab(bot: Bot):
    """Проверяет раздачи Fab.com и публикует новые ассеты."""
    logger.info("Запуск автоматической проверки раздач Fab.com...")
    
    from src.api.fab_client import FabClient
    from src.bot.channels import ChannelsManager
    from src.bot.publisher import escape_markdown
    
    fab_client = FabClient()
    history = HistoryManager()
    channels_manager = ChannelsManager()
    
    try:
        data = await fab_client.get_fab_freebies()
        if not data or not data.get("assets"):
            logger.info("Активных раздач на Fab.com не найдено.")
            return
            
        new_assets = []
        for asset in data["assets"]:
            asset_id = asset.get("id")
            if not asset_id:
                asset_id = asset["url"].split("/")[-1]
                asset["id"] = asset_id
                
            if not history.is_published(asset_id):
                new_assets.append(asset)
            else:
                logger.info("Ассет '%s' (ID: %s) уже публиковался ранее. Пропуск.", asset["title"], asset_id)
                
        if not new_assets:
            logger.info("Новых раздач на Fab.com для публикации не найдено.")
            return
            
        logger.info("Найдено новых ассетов Fab: %d. Формирование публикации...", len(new_assets))
        
        header = (
            f"📦 *НОВЫЕ БЕСПЛАТНЫЕ МАТЕРИАЛЫ FAB* 📦\n\n"
            f"🔥 *Список новых бесплатных материалов на Fab\\.com:*\n\n"
        )
        
        body_parts = []
        for idx, asset in enumerate(new_assets, start=1):
            asset_title = escape_markdown(asset["title"])
            asset_url = asset["url"].replace("(", "\\(").replace(")", "\\)")
            author = escape_markdown(asset.get("author", "Неизвестно"))
            
            desc = asset.get("description", "").strip()
            if desc:
                desc_esc = escape_markdown(desc)
                item_text = (
                    f"🔥 *{idx}\\. [{asset_title}]({asset_url})*\n"
                    f"👤 Автор: *{author}*\n"
                    f"📖 _Описание: {desc_esc}_"
                )
            else:
                item_text = (
                    f"🔥 *{idx}\\. [{asset_title}]({asset_url})*\n"
                    f"👤 Автор: *{author}*"
                )
            body_parts.append(item_text)
            
        body = "\n\n".join(body_parts)
        footer = (
            f"\n\n👉 Заберите их на странице [Fab Limited\\-Time Free](https://www.fab.com/limited-time-free) "
            f"или в Unreal Engine Editor в разделе Fab\\!"
        )
        text = f"{header}{body}{footer}"
        
        target_chats = set()
        if settings.channel_id:
            target_chats.add(settings.channel_id)
            
        for ch_id in channels_manager.get_channels().keys():
            try:
                target_chats.add(int(ch_id))
            except ValueError:
                target_chats.add(ch_id)
                
        published_count = 0
        for chat_id in target_chats:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="MarkdownV2",
                    disable_web_page_preview=True
                )
                published_count += 1
            except Exception as e:
                logger.error("Ошибка при публикации Fab в чат %s: %s", chat_id, str(e))
                
        if published_count > 0:
            for asset in new_assets:
                history.mark_as_published(asset["id"], asset["title"])
            logger.info("Автоматическая проверка Fab завершена. Опубликовано новых ассетов: %d в %d чатов", len(new_assets), published_count)
        else:
            logger.error("Не удалось опубликовать ассеты Fab ни в один чат.")
            
    except Exception as e:
        logger.exception("Ошибка в фоновой проверке Fab: %s", str(e))

async def check_and_publish_daily(bot: Bot):
    """Задача планировщика: проверяет EGS API и Fab.com и публикует новые раздачи."""
    logger.info("Запуск автоматической проверки раздач...")
    
    try:
        games = await epic_client.get_free_games()
        if not games:
            logger.info("Активных бесплатных раздач не найдено.")
            return

        history = HistoryManager()
        new_games = []

        for game in games:
            game_id = game["id"]
            title = game["title"]
            
            # Проверяем, была ли эта игра уже отправлена
            if history.is_published(game_id):
                logger.info("Игра '%s' (ID: %s) уже публиковалась ранее. Пропуск.", title, game_id)
                continue
                
            new_games.append(game)
            
        if new_games:
            logger.info("Найдено новых раздач: %d. Публикация...", len(new_games))
            
            # Собираем все каналы и группы для публикации
            from src.bot.channels import ChannelsManager
            channels_manager = ChannelsManager()
            
            target_chats = set()
            if settings.channel_id:
                target_chats.add(settings.channel_id)
                
            for ch_id in channels_manager.get_channels().keys():
                try:
                    target_chats.add(int(ch_id))
                except ValueError:
                    target_chats.add(ch_id)
            
            published_count = 0
            for chat_id in target_chats:
                try:
                    success = await publish_games(bot, chat_id, new_games)
                    if success:
                        published_count += 1
                except Exception as e:
                    logger.error("Ошибка при авто-публикации в чат %s: %s", chat_id, str(e))
                    
            if published_count > 0:
                # Фиксируем все опубликованные игры в истории
                for game in new_games:
                    history.mark_as_published(game["id"], game["title"])
                logger.info("Автоматическая проверка завершена. Опубликовано новых игр: %d в %d чатов", len(new_games), published_count)
            else:
                logger.error("Не удалось опубликовать новые раздачи ни в один чат.")
        else:
            logger.info("Новых раздач для публикации не найдено.")
        
    except Exception as e:
        logger.exception("Ошибка в фоновой задаче планировщика check_and_publish_daily: %s", str(e))
        
    try:
        await check_and_publish_fab(bot)
    except Exception as e:
        logger.exception("Ошибка при авто-проверке раздач Fab: %s", str(e))

def setup_scheduler(bot: Bot):
    """Настраивает и запускает планировщик задач."""
    # Парсим время проверки из настроек (по умолчанию "18:00")
    try:
        time_parts = settings.check_time.split(":")
        hour = int(time_parts[0])
        minute = int(time_parts[1])
    except (ValueError, IndexError):
        logger.warning(
            "Некорректный формат времени проверки CHECK_TIME: '%s'. "
            "Используется время по умолчанию 18:00.", 
            settings.check_time
        )
        hour, minute = 18, 0

    # Настраиваем ежедневную задачу по времени
    scheduler.add_job(
        check_and_publish_daily,
        trigger=CronTrigger(hour=hour, minute=minute),
        args=[bot],
        id="daily_check",
        replace_existing=True
    )
    
    # Дополнительно запускаем одну проверку через 5 секунд после старта бота,
    # чтобы не упустить раздачи, если бот был выключен во время плановой проверки.
    start_time = datetime.now() + timedelta(seconds=5)
    scheduler.add_job(
        check_and_publish_daily,
        trigger="date",
        run_date=start_time,
        args=[bot],
        id="startup_check",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(
        "Планировщик задач успешно запущен. Ежедневная проверка настроена на %02d:%02d.", 
        hour, 
        minute
    )
