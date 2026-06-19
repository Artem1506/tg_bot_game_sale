import json
import logging
from datetime import datetime, timezone
from src.config import settings

logger = logging.getLogger(__name__)

class HistoryManager:
    """Класс для управления историей опубликованных раздач."""

    def __init__(self):
        self.file_path = settings.history_file
        self.history = self._load_history()

    def _load_history(self) -> dict:
        """Загружает историю из JSON-файла.
        
        Returns:
            dict: Словарь опубликованных игр.
        """
        if not self.file_path.exists():
            return {}
            
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                else:
                    logger.warning("Некорректный формат файла истории. Сброс до пустого словаря.")
                    return {}
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Ошибка при чтении файла истории раздач: %s. Создаем новый.", str(e))
            return {}

    def _save_history(self):
        """Сохраняет историю в JSON-файл."""
        try:
            # Создаем родительские директории, если их нет
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=4)
        except IOError as e:
            logger.error("Не удалось сохранить файл истории раздач: %s", str(e))

    def is_published(self, game_id: str) -> bool:
        """Проверяет, публиковалась ли раздача ранее.
        
        Args:
            game_id (str): Уникальный ID игры.
            
        Returns:
            bool: True, если игра уже публиковалась, иначе False.
        """
        return game_id in self.history

    def mark_as_published(self, game_id: str, title: str):
        """Помечает раздачу как опубликованную и сохраняет изменения.
        
        Args:
            game_id (str): Уникальный ID игры.
            title (str): Название игры для удобства чтения JSON-файла человеком.
        """
        self.history[game_id] = {
            "title": title,
            "published_at": datetime.now(timezone.utc).isoformat()
        }
        self._save_history()
        logger.info("Игра '%s' (ID: %s) успешно добавлена в историю публикаций.", title, game_id)
