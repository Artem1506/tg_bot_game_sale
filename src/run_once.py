import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Добавляем корень проекта в sys.path, чтобы импорты 'from src.xxx' работали корректно
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
from aiogram import Bot
from src.config import settings
from src.api.epic_client import EpicGamesClient
from src.bot.history import HistoryManager
from src.bot.publisher import publish_games

def setup_logging():
    """Настраивает логирование в файлы и консоль."""
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    file_handler = RotatingFileHandler(
        filename=settings.log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(fmt=log_format, datefmt=date_format))
    
    # Настройка FileHandler для текстового файла в корне проекта
    root_log_file = ROOT_DIR / "bot_activity.log"
    root_file_handler = logging.FileHandler(
        filename=root_log_file,
        encoding="utf-8"
    )
    root_file_handler.setFormatter(logging.Formatter(fmt=log_format, datefmt=date_format))
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(fmt=log_format, datefmt=date_format))
    
    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, root_file_handler, console_handler]
    )
    
    # Отключаем лишний шум
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)

async def run_once():
    """Разовый запуск: проверяет раздачи, шлет новые в канал и завершает процесс."""
    setup_logging()
    logger = logging.getLogger("run_once")
    logger.info("Старт разовой проверки раздач...")

    if not settings.bot_token:
        logger.error("Запуск невозможен: отсутствует BOT_TOKEN. Завершение.")
        return

    bot = Bot(token=settings.bot_token)
    epic_client = EpicGamesClient()
    history = HistoryManager()

    try:
        # 1. Проверяем раздачи EGS
        try:
            games = await epic_client.get_free_games()
            if not games:
                logger.info("Активных раздач EGS не обнаружено.")
            else:
                new_games = []
                for game in games:
                    if not history.is_published(game["id"]):
                        new_games.append(game)
                    else:
                        logger.info("Игра '%s' уже была опубликована. Пропуск.", game["title"])
                
                if new_games:
                    logger.info("Найдено новых игр для публикации: %d", len(new_games))
                    success = await publish_games(bot, settings.channel_id, new_games)
                    if success:
                        for game in new_games:
                            history.mark_as_published(game["id"], game["title"])
                        logger.info("Все новые игры успешно опубликованы в канал.")
                    else:
                        logger.error("Ошибка при публикации новых игр в канал.")
                else:
                    logger.info("Все найденные игры уже есть в истории. Публикация не требуется.")
        except Exception as e:
            logger.exception("Ошибка при проверке раздач EGS: %s", str(e))
            
        # 2. Проверяем раздачи Fab
        try:
            from src.bot.scheduler import check_and_publish_fab
            await check_and_publish_fab(bot)
        except Exception as e:
            logger.exception("Ошибка при проверке раздач Fab: %s", str(e))

    except Exception as e:
        logger.exception("Критическая ошибка при разовом запуске: %s", str(e))
    finally:
        # Обязательно закрываем сессию бота
        await bot.session.close()
        logger.info("Разовая проверка завершена. Сессия закрыта.")

if __name__ == "__main__":
    asyncio.run(run_once())
