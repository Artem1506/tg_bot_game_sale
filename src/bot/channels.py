import json
import logging
from src.config import settings

logger = logging.getLogger(__name__)

class ChannelsManager:
    """Класс для управления списком каналов и чатов, в которые добавлен бот."""

    def __init__(self):
        self.file_path = settings.channels_file
        self.channels = self._load_channels()

    def _load_channels(self) -> dict:
        """Загружает список каналов из JSON-файла.
        
        Returns:
            dict: Словарь с каналами: {str(channel_id): {"title": title, "type": type}}
        """
        if not self.file_path.exists():
            return {}
            
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                else:
                    logger.warning("Некорректный формат файла каналов. Сброс до пустого словаря.")
                    return {}
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Ошибка при чтении файла каналов: %s. Создаем новый.", str(e))
            return {}

    def _save_channels(self):
        """Сохраняет список каналов в JSON-файл."""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.channels, f, ensure_ascii=False, indent=4)
        except IOError as e:
            logger.error("Не удалось сохранить файл каналов: %s", str(e))

    def add_channel(self, channel_id: int, title: str, chat_type: str):
        """Добавляет или обновляет канал/группу в списке.
        
        Args:
            channel_id (int): ID канала/чата.
            title (str): Название канала/чата.
            chat_type (str): Тип чата (channel, group, supergroup).
        """
        channel_id_str = str(channel_id)
        existing = self.channels.get(channel_id_str)
        if existing and existing.get("title") == title and existing.get("type") == chat_type:
            return  # Изменений нет, пропускаем перезапись файла
            
        self.channels[channel_id_str] = {
            "title": title,
            "type": chat_type
        }
        self._save_channels()
        logger.info("Канал/группа '%s' (ID: %s, тип: %s) добавлен/обновлен в списке.", title, channel_id, chat_type)

    def remove_channel(self, channel_id: int):
        """Удаляет канал из списка.
        
        Args:
            channel_id (int): ID канала/чата.
        """
        channel_id_str = str(channel_id)
        if channel_id_str in self.channels:
            title = self.channels[channel_id_str].get("title", "Неизвестный")
            del self.channels[channel_id_str]
            self._save_channels()
            logger.info("Канал '%s' (ID: %s) удален из списка.", title, channel_id)

    def get_channels(self) -> dict:
        """Возвращает копию словаря всех известных каналов."""
        return dict(self.channels)
