import logging
import asyncio
from datetime import datetime, timezone
import aiohttp
from src.config import settings

logger = logging.getLogger(__name__)

class EpicGamesClient:
    """Клиент для работы с публичным API Epic Games Store."""

    def __init__(self):
        self.api_url = settings.epic_api_url
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

    async def get_free_games(self) -> list[dict]:
        """Получает список бесплатных игр, раздаваемых в данный момент.
        
        Реализует повторные попытки с экспоненциальной задержкой при сбоях сети.
        
        Returns:
            list[dict]: Список словарей с данными о бесплатных играх.
        """
        params = {
            "locale": "ru",
            "country": "US"
        }
        
        max_retries = 3
        backoff_factor = 2
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info("Запрос к Epic Games API (попытка %d/%d)...", attempt, max_retries)
                async with aiohttp.ClientSession(headers=self.headers) as session:
                    async with session.get(self.api_url, params=params, timeout=15) as response:
                        if response.status != 200:
                            raise aiohttp.ClientResponseError(
                                request_info=response.request_info,
                                history=response.history,
                                status=response.status,
                                message=f"Некорректный статус ответа: {response.status}"
                            )
                        
                        data = await response.json()
                        return self._parse_games(data)
                        
            except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
                logger.warning("Ошибка при запросе к API Epic Games: %s", str(e))
                if attempt == max_retries:
                    logger.error("Все попытки запроса к API Epic Games исчерпаны.")
                    return []
                
                sleep_time = backoff_factor ** attempt
                logger.info("Ожидание %d сек перед повторным запросом...", sleep_time)
                await asyncio.sleep(sleep_time)
                
        return []

    def _parse_games(self, data: dict) -> list[dict]:
        """Парсит JSON-ответ от API Epic Games и отбирает активные раздачи.
        
        Args:
            data (dict): Сырой JSON-ответ от API.
            
        Returns:
            list[dict]: Список отфильтрованных игр с необходимыми полями.
        """
        parsed_games = []
        
        try:
            elements = data["data"]["Catalog"]["searchStore"]["elements"]
        except (KeyError, TypeError) as e:
            logger.error("Некорректная структура JSON-ответа от API: %s", str(e))
            return []

        now = datetime.now(timezone.utc)
        
        for el in elements:
            try:
                title = el.get("title", "Без названия")
                game_id = el.get("id", "")
                if not game_id:
                    continue
                
                # Проверяем наличие блока промоакций
                promotions = el.get("promotions")
                if not promotions or not isinstance(promotions, dict):
                    continue
                
                promotional_offers = promotions.get("promotionalOffers")
                if not promotional_offers or not isinstance(promotional_offers, list):
                    continue
                
                # Ищем активную акцию со 100% скидкой (бесплатно)
                is_free_now = False
                active_offer = None
                
                for group in promotional_offers:
                    offers = group.get("promotionalOffers", [])
                    for offer in offers:
                        discount_setting = offer.get("discountSetting", {})
                        discount_type = discount_setting.get("discountType")
                        discount_value = discount_setting.get("discountValue")
                        discount_percentage = discount_setting.get("discountPercentage")
                        
                        # В Epic Games Store 100% скидка обозначается как discountPercentage == 0 (оставшаяся цена 0%)
                        # или в некоторых случаях discountValue == 0
                        is_free = (discount_percentage == 0) or (discount_value == 0)
                        
                        if is_free:
                            start_str = offer.get("startDate", "")
                            end_str = offer.get("endDate", "")
                            
                            if start_str and end_str:
                                # Преобразуем строки дат в datetime с временной зоной UTC
                                # Заменяем 'Z' на '+00:00' для совместимости с fromisoformat в старых Python
                                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                                
                                if start_dt <= now <= end_dt:
                                    is_free_now = True
                                    active_offer = offer
                                    break
                    if is_free_now:
                        break
                        
                if not is_free_now or not active_offer:
                    continue
                
                # Извлекаем данные игры
                description = el.get("description", "").strip()
                if not description:
                    # Попытаемся найти альтернативное описание
                    description = el.get("customAttributes", {}).get("description", "")
                
                # Ищем обложку (сначала широкоформатную, потом обычную)
                image_url = ""
                images = el.get("keyImages", [])
                
                # Сначала ищем OfferImageWide (лучше для постов Telegram)
                for img in images:
                    if img.get("type") == "OfferImageWide":
                        image_url = img.get("url", "")
                        break
                
                # Если широкоформатной нет, ищем Thumbnail или любую картинку
                if not image_url:
                    for img in images:
                        if img.get("type") in ("Thumbnail", "DieselStoreFrontWide"):
                            image_url = img.get("url", "")
                            break
                if not image_url and images:
                    image_url = images[0].get("url", "")
                    
                # Формируем ссылку на EGS
                # Порядок поиска слага для ссылки: productSlug -> urlSlug -> mappings[0].pageSlug
                slug = el.get("productSlug") or el.get("urlSlug")
                if not slug:
                    # Проверяем mappings
                    mappings = el.get("catalogNs", {}).get("mappings", [])
                    if mappings and isinstance(mappings, list):
                        slug = mappings[0].get("pageSlug")
                
                # Если слаг все еще пустой, но есть slug в customAttributes
                if not slug:
                    for attr in el.get("customAttributes", []):
                        if attr.get("key") == "productSlug":
                            slug = attr.get("value")
                            break
                            
                # Если совсем ничего нет, используем заглушку
                if slug:
                    # Убираем лишние слэши, если они есть
                    slug = slug.strip("/")
                    game_url = f"https://store.epicgames.com/ru/p/{slug}"
                else:
                    game_url = "https://store.epicgames.com/ru/free-games"

                # Даты начала и конца раздачи для отображения
                start_dt = datetime.fromisoformat(active_offer["startDate"].replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(active_offer["endDate"].replace("Z", "+00:00"))

                parsed_games.append({
                    "id": game_id,
                    "title": title,
                    "description": description,
                    "image_url": image_url,
                    "url": game_url,
                    "start_date": start_dt,
                    "end_date": end_dt
                })
                logger.info("Найдена бесплатная игра: %s (до %s)", title, end_dt.strftime("%d.%m.%Y %H:%M"))
                
            except Exception as e:
                logger.exception("Ошибка при парсинге элемента игры: %s", str(e))
                continue
                
        return parsed_games
