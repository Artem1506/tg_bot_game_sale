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

async def check_and_publish_daily(bot: Bot):
    """Задача планировщика: проверяет EGS API и публикует новые раздачи."""
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
            logger.info("Найдено новых раздач: %d. Публикация в канал...", len(new_games))
            success = await publish_games(bot, settings.channel_id, new_games)
            if success:
                # Фиксируем все опубликованные игры в истории
                for game in new_games:
                    history.mark_as_published(game["id"], game["title"])
                logger.info("Автоматическая проверка завершена. Опубликовано новых игр: %d", len(new_games))
            else:
                logger.error("Не удалось опубликовать новые раздачи.")
        else:
            logger.info("Новых раздач для публикации не найдено.")
        
    except Exception as e:
        logger.exception("Ошибка в фоновой задаче планировщика check_and_publish_daily: %s", str(e))

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
