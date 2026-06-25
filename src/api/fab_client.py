import logging
import asyncio
import re
import urllib.parse
import sys
import html as html_mod

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
                              "author": "Имя автора",
                              "description": "Описание ассета"
                          },
                          ...
                      ]
                  }
        """
        try:
            logger.info("Запуск curl для загрузки страницы раздач Fab.com...")
            
            # Запускаем curl асинхронно
            process = await asyncio.create_subprocess_exec(
                "curl", "-s", "-A", self.user_agent, self.url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error("curl завершился с ошибкой (код %d): %s", process.returncode, stderr.decode("utf-8", errors="ignore"))
                return {}
                
            html = stdout.decode("utf-8", errors="ignore")
            logger.info("Страница Fab.com успешно загружена. Размер: %d символов.", len(html))
            
            data = self._parse_html(html)
            assets = data.get("assets", [])
            
            if not assets:
                return {}
                
            # Асинхронно загружаем описание для каждого ассета
            logger.info("Запуск параллельного сбора описаний для %d ассетов...", len(assets))
            tasks = []
            for asset in assets:
                asset_id = asset["url"].split("/")[-1]
                tasks.append(self._get_asset_description(asset_id))
                
            descriptions = await asyncio.gather(*tasks)
            
            for asset, desc in zip(assets, descriptions):
                asset["description"] = desc
                
            logger.info("Сбор описаний завершен.")
            return {"assets": assets}
            
        except Exception as e:
            logger.exception("Критическая ошибка при получении данных с Fab.com: %s", str(e))
            return {}

    async def _get_asset_description(self, asset_id: str) -> str:
        """Загружает страницу ассета и извлекает описание из мета-тегов."""
        url = f"https://www.fab.com/listings/{asset_id}"
        try:
            logger.info("Загрузка страницы ассета %s...", asset_id)
            process = await asyncio.create_subprocess_exec(
                "curl", "-s", "-A", self.user_agent, url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error("curl завершился с ошибкой при запросе ассета %s", asset_id)
                return ""
                
            html_content = stdout.decode("utf-8", errors="ignore")
            
            # Ищем meta description или og:description
            match = re.search(r'<meta name="description" content="([^"]+)"', html_content)
            if not match:
                match = re.search(r'<meta property="og:description" content="([^"]+)"', html_content)
                
            if match:
                desc = match.group(1).strip()
                # Декодируем спецсимволы HTML (&quot;, &#34; и т.д.) с учетом возможного двойного экранирования
                desc_clean = html_mod.unescape(html_mod.unescape(desc))
                # Убираем лишние переносы строк и пробелы
                desc_clean = re.sub(r'\s+', ' ', desc_clean)
                
                # Обрезаем описание до 200 символов
                if len(desc_clean) > 200:
                    return desc_clean[:197] + "..."
                return desc_clean
                
            return ""
        except Exception as e:
            logger.error("Ошибка при извлечении описания ассета %s: %s", asset_id, str(e))
            return ""

    def _parse_html(self, html: str) -> dict:
        """Парсит HTML-код страницы раздач Fab.com с помощью регулярных выражений.
        
        Args:
            html (str): HTML-код страницы.
            
        Returns:
            dict: Структурированные данные о раздаваемых ассетах (без описаний).
        """
        pattern = re.compile(
            r'href="/listings/([a-f0-9-]+)"[^>]*>.*?<div[^>]*class="fabkit-Typography-ellipsisWrapper"[^>]*>([^<]+)</div>.*?</a>'
            r'(?:.*?href="/sellers/([^"]+)"[^>]*>.*?<div[^>]*class="fabkit-Typography-ellipsisWrapper"[^>]*>([^<]+)</div>.*?</a>)?',
            re.DOTALL
        )
        
        matches = pattern.findall(html)
        
        assets = []
        seen_ids = set()
        
        for item_id, title, seller_slug, seller_name in matches:
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                title = title.strip()
                seller_name = seller_name.strip() if seller_name else "Неизвестно"
                
                assets.append({
                    "id": item_id,
                    "title": title,
                    "url": f"https://www.fab.com/listings/{item_id}",
                    "author": seller_name
                })
                
        return {"assets": assets}
