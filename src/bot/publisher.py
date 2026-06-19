import logging
from datetime import datetime
from aiogram import Bot
from aiogram.types import InputMediaPhoto
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)

def escape_markdown(text: str) -> str:
    """Экранирует специальные символы для Telegram MarkdownV2.
    
    Args:
        text (str): Исходный текст.
        
    Returns:
        str: Экранированный текст.
    """
    if not text:
        return ""
    # Символы, которые необходимо экранировать в MarkdownV2
    escape_chars = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{char}" if char in escape_chars else char for char in text)

def format_date(dt: datetime) -> str:
    """Форматирует дату в человекочитаемый вид (ДД.ММ.ГГГГ в 18:00)."""
    return dt.strftime("%d.%m.%Y в %H:%M")

def build_single_post_text(game_data: dict) -> str:
    """Формирует текст публикации для одной игры в формате MarkdownV2."""
    title = escape_markdown(game_data["title"])
    description = game_data["description"]
    url = game_data["url"]
    
    start_str = format_date(game_data["start_date"])
    end_str = format_date(game_data["end_date"])
    
    start_str_esc = escape_markdown(start_str)
    end_str_esc = escape_markdown(end_str)
    url_esc = url.replace("(", "\\(").replace(")", "\\)")
    
    header = f"🎮 *{title}*\n\n"
    footer = (
        f"\n\n📅 *Период раздачи:*\n"
        f"C {start_str_esc} до {end_str_esc} \\(МСК\\)\n\n"
        f"🔗 [Забрать игру в Epic Games Store]({url_esc})"
    )
    
    max_desc_len = 1024 - len(header) - len(footer) - 50
    if len(description) > max_desc_len:
        truncated_desc = description[:max_desc_len - 3] + "..."
    else:
        truncated_desc = description
        
    desc_esc = escape_markdown(truncated_desc)
    return f"{header}{desc_esc}{footer}"

def build_multiple_post_text(games: list[dict]) -> str:
    """Формирует объединенный текст для публикации нескольких игр в одном посте."""
    header = "🎮 *БЕСПЛАТНЫЕ ИГРЫ В EPIC GAMES STORE* 🎮\n\n"
    
    # Даты берем из первой игры раздачи
    start_str = format_date(games[0]["start_date"])
    end_str = format_date(games[0]["end_date"])
    
    start_str_esc = escape_markdown(start_str)
    end_str_esc = escape_markdown(end_str)
    
    footer = (
        f"\n📅 *Период раздачи:*\n"
        f"C {start_str_esc} до {end_str_esc} \\(МСК\\)"
    )
    
    # Лимит подписи в Telegram - 1024 символа. Вычисляем доступное место для описаний.
    fixed_len = len(header) + len(footer) + 50
    available_for_desc = 1024 - fixed_len
    # Распределяем доступное место поровну между играми
    max_desc_per_game = max(150, available_for_desc // len(games))
    
    body_parts = []
    for idx, game in enumerate(games, start=1):
        title = escape_markdown(game["title"])
        description = game["description"]
        url = game["url"]
        url_esc = url.replace("(", "\\(").replace(")", "\\)")
        
        if len(description) > max_desc_per_game:
            truncated_desc = description[:max_desc_per_game - 3] + "..."
        else:
            truncated_desc = description
        desc_esc = escape_markdown(truncated_desc)
        
        game_part = (
            f"🔥 *{idx}\. {title}*\n"
            f"{desc_esc}\n"
            f"🔗 [Забрать игру]({url_esc})"
        )
        body_parts.append(game_part)
        
    body = "\n\n".join(body_parts)
    return f"{header}{body}\n\n{footer}"

async def publish_game(bot: Bot, chat_id: int | str, game_data: dict) -> bool:
    """Вспомогательный метод для публикации ровно одной игры с фото."""
    text = build_single_post_text(game_data)
    image_url = game_data.get("image_url")
    
    try:
        if image_url:
            await bot.send_photo(chat_id=chat_id, photo=image_url, caption=text, parse_mode="MarkdownV2")
        else:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="MarkdownV2", disable_web_page_preview=False)
        return True
    except TelegramAPIError as e:
        logger.error("Ошибка Telegram API при отправке одиночного поста: %s", str(e))
        if image_url:
            try:
                await bot.send_message(chat_id=chat_id, text=text, parse_mode="MarkdownV2", disable_web_page_preview=False)
                return True
            except TelegramAPIError:
                pass
        return False

async def publish_games(bot: Bot, chat_id: int | str, games: list[dict]) -> bool:
    """Отправляет пост с бесплатными играми в Telegram.
    
    Если игра одна, она отправляется как одиночное фото с описанием.
    Если игр несколько, они отправляются как альбом (Media Group) с общим 
    описанием под первым фото.
    """
    if not games:
        return False
        
    if len(games) == 1:
        return await publish_game(bot, chat_id, games[0])
        
    # Формируем объединенный текст поста
    text = build_multiple_post_text(games)
    
    # Собираем медиагруппу (альбом фото)
    media_group = []
    for idx, game in enumerate(games):
        image_url = game.get("image_url")
        if not image_url:
            continue
            
        # Прикрепляем текст (caption) и разметку только к первому элементу альбома
        caption = text if idx == 0 else None
        parse_mode = "MarkdownV2" if idx == 0 else None
        
        media_group.append(
            InputMediaPhoto(
                media=image_url,
                caption=caption,
                parse_mode=parse_mode
            )
        )
        
    try:
        if media_group:
            logger.info("Отправка альбома с %d играми в чат %s...", len(games), chat_id)
            await bot.send_media_group(chat_id=chat_id, media=media_group)
        else:
            logger.info("Отправка объединенного текста без фото в чат %s...", chat_id)
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True
            )
        return True
    except TelegramAPIError as e:
        logger.error("Ошибка Telegram API при отправке медиагруппы: %s", str(e))
        # Фолбек: пытаемся отправить просто как текстовое сообщение без фото
        try:
            logger.info("Попытка отправить объединенный пост текстом без фото...")
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True
            )
            return True
        except TelegramAPIError as e2:
            logger.error("Повторная ошибка при отправке текста: %s", str(e2))
        return False
    except Exception as e:
        logger.exception("Непредвиденная ошибка при публикации раздачи: %s", str(e))
        return False
