import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env в корне проекта
ROOT_DIR = Path(__file__).resolve().parent.parent
env_path = ROOT_DIR / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)

class Settings:
    """Класс настроек конфигурации приложения (Singleton)."""
    
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Settings, cls).__new__(cls)
            cls._instance._init_settings()
        return cls._instance

    def _init_settings(self):
        self.bot_token: str = os.getenv("BOT_TOKEN", "")
        
        # ID канала может быть строкой или числом (например, -100xxx)
        channel_id_str = os.getenv("CHANNEL_ID", "")
        try:
            self.channel_id: int = int(channel_id_str)
        except ValueError:
            # Если это строка (например, юзернейм канала с @)
            self.channel_id: str = channel_id_str if channel_id_str.startswith("@") else f"@{channel_id_str}"
            
        self.epic_api_url: str = os.getenv(
            "EPIC_API_URL", 
            "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
        )
        
        # ID администраторов. Задаются через запятую в .env: ADMIN_IDS=12345,67890
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        self.admin_ids: set[int] = set()
        if admin_ids_str:
            for admin_id in admin_ids_str.split(","):
                try:
                    self.admin_ids.add(int(admin_id.strip()))
                except ValueError:
                    logger.warning("Некорректный ID администратора в .env: %s", admin_id)

        # Время ежедневной проверки раздач в формате HH:MM
        self.check_time: str = os.getenv("CHECK_TIME", "18:00")
        
        # Путь к файлу с историей раздач
        self.history_file: Path = ROOT_DIR / "history.json"
        
        # Путь к лог-файлам
        self.log_dir: Path = ROOT_DIR / "logs"
        self.log_file: Path = self.log_dir / "app.log"
        
        # Валидация критических настроек
        if not self.bot_token:
            logger.error("Переменная BOT_TOKEN не задана в файле .env!")
        if not channel_id_str:
            logger.error("Переменная CHANNEL_ID не задана в файле .env!")

# Создаем глобальный объект настроек для импорта в других модулях
settings = Settings()
