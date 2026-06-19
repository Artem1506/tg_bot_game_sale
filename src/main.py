import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Добавляем корень проекта в sys.path, чтобы импорты 'from src.xxx' работали при любом типе запуска
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
from aiogram import Bot, Dispatcher
from src.config import settings
from src.bot.handlers import router as bot_router
from src.bot.scheduler import setup_scheduler

def setup_logging():
    """Настраивает логирование в файл с ротацией и вывод в консоль."""
    # Создаем директорию для логов, если её нет
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Настройка RotatingFileHandler (максимум 5 файлов по 5 МБ каждый)
    file_handler = RotatingFileHandler(
        filename=settings.log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(fmt=log_format, datefmt=date_format))
    
    # Настройка консольного вывода
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(fmt=log_format, datefmt=date_format))
    
    # Базовая конфигурация корневого логгера
    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, console_handler]
    )
    
    # Понижаем уровень шума для сторонних библиотек
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)

async def main():
    # Инициализация логирования
    setup_logging()
    logger = logging.getLogger("main")
    logger.info("Запуск Epic Free Games Bot...")

    if not settings.bot_token:
        logger.error("Запуск невозможен: отсутствует BOT_TOKEN. Завершение работы.")
        return

    # Инициализируем бота и диспетчер
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()

    # Подключаем обработчики команд
    dp.include_router(bot_router)

    # Настраиваем планировщик задач
    setup_scheduler(bot)

    # Запускаем поллинг (опрос серверов Telegram)
    try:
        logger.info("Бот запущен и готов к приему сообщений. Запуск polling...")
        # Сбрасываем накопившиеся за время офлайна апдейты перед запуском
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.exception("Критическая ошибка при работе бота: %s", str(e))
    finally:
        # Закрываем сессию бота при выходе
        await bot.session.close()
        logger.info("Сессия бота закрыта. Работа завершена.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger("main").info("Бот остановлен вручную.")
