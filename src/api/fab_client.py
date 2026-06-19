import logging
import asyncio
import re
import urllib.parse
import sys

logger = logging.getLogger(__name__)

class FabClient:
    """Клиент для получения бесплатных ассетов с Fab.com."""

    def __init__(self):
        self.url = "https://www.fab.com/limited-time-free"
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    async def get_fab_freebies(self) -> dict:
        """Получает список бесплатных ассетов с Fab.com, запуская системную утилиту curl.
        
        Returns:
            dict: Словарь с результатами поиска или пустой словарь.
                  Формат: {
                      "assets": [
                          {
                              "title": "Название ассета",
                              "url": "Ссылка на ассет",
                              "author": "Имя автора"
                          },
                          ...
                      ]
                  }
        """
        try:
            logger.info("Запуск curl для загрузки страницы раздач Fab.com...")
            
            # Запускаем curl асинхронно
            # Ключ -s отключает индикатор прогресса, -A задает User-Agent
            process = await asyncio.create_subprocess_exec(
                "curl", "-s", "-A", self.user_agent, self.url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error("curl завершился с ошибкой (код %d): %s", process.returncode, stderr.decode("utf-8", errors="ignore"))
                return {}
                
            # Декодируем вывод. Страница обычно в UTF-8.
            html = stdout.decode("utf-8", errors="ignore")
            logger.info("Страница Fab.com успешно загружена. Размер: %d символов. Начинаю парсинг...", len(html))
            
            return self._parse_html(html)
            
        except Exception as e:
            logger.exception("Критическая ошибка при вызове curl для Fab.com: %s", str(e))
            return {}

    def _parse_html(self, html: str) -> dict:
        """Парсит HTML-код страницы раздач Fab.com с помощью регулярных выражений.
        
        Args:
            html (str): HTML-код страницы.
            
        Returns:
            dict: Структурированные данные о раздаваемых ассетах.
        """
        # Шаблон для поиска:
        # 1. Ссылка на listing и название ассета
        # 2. Опционально идущая следом ссылка на seller и имя автора
        pattern = re.compile(
            r'href="/listings/([a-f0-9-]+)"[^>]*>.*?<div[^>]*class="fabkit-Typography-ellipsisWrapper"[^>]*>([^<]+)</div>.*?</a>'
            r'(?:.*?href="/sellers/([^"]+)"[^>]*>.*?<div[^>]*class="fabkit-Typography-ellipsisWrapper"[^>]*>([^<]+)</div>.*?</a>)?',
            re.DOTALL
        )
        
        matches = pattern.findall(html)
        logger.info("Всего совпадений по регулярному выражению: %d", len(matches))
        
        assets = []
        seen_ids = set()
        
        for item_id, title, seller_slug, seller_name in matches:
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                title = title.strip()
                seller_name = seller_name.strip() if seller_name else "Неизвестно"
                
                assets.append({
                    "title": title,
                    "url": f"https://www.fab.com/listings/{item_id}",
                    "author": seller_name
                })
                
        logger.info("Успешно извлечено уникальных ассетов: %d", len(assets))
        return {"assets": assets}
