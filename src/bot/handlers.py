import logging
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from src.config import settings
from src.api.epic_client import EpicGamesClient
from src.bot.publisher import publish_games, escape_markdown
from src.api.fab_client import FabClient

logger = logging.getLogger(__name__)
router = Router()
epic_client = EpicGamesClient()
fab_client = FabClient()

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором бота."""
    return user_id in settings.admin_ids

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start."""
    user_id = message.from_user.id
    is_user_admin = is_admin(user_id)
    
    admin_status = "Администратор 🛠️" if is_user_admin else "Пользователь 👤"
    
    welcome_text = (
        f"👋 Привет, *{escape_markdown(message.from_user.first_name)}*\!\n\n"
        f"Я бот для отслеживания бесплатных игр в Epic Games Store\.\n"
        f"Мой статус для вас: *{admin_status}*\n"
        f"Ваш Telegram ID: `{user_id}` \\(скопируйте его для добавления в ADMIN\_IDS в `.env` при необходимости\\)\n\n"
    )
    
    if is_user_admin:
        welcome_text += (
            "Доступные команды:\n"
            "• `/check` — Проверить раздачи игр и прислать превью в ЛС\.\n"
            "• `/check channel` — Опубликовать раздачи игр в канал\.\n"
            "• `/check_fab` — Проверить раздачи FAB и прислать превью в ЛС\.\n"
            "• `/check_fab channel` — Опубликовать раздачи FAB в канал\.\n"
            "• `/help` — Справка по командам\."
        )
    else:
        welcome_text += "Вы можете использовать меня для мониторинга раздач в канале @grampsgamer\."

    await message.answer(welcome_text, parse_mode="MarkdownV2")

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help."""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("У вас нет прав для просмотра административных команд.")
        return
        
    help_text = (
        "ℹ️ *Справка по командам администратора*\n\n"
        "• `/check` — выполняет запрос к Epic Games API и присылает все активные "
        "бесплатные раздачи игр в этот чат в качестве *превью*.\n\n"
        "• `/check channel` — выполняет запрос к Epic Games API и *публикует* "
        "раздачи игр в Telegram-канал.\n\n"
        "• `/check_fab` — ищет информацию о раздачах FAB на Reddit и присылает список "
        "ассетов в этот чат в качестве *превью*.\n\n"
        "• `/check_fab channel` — публикует список бесплатных ассетов FAB в Telegram-канал."
    )
    await message.answer(help_text, parse_mode="Markdown")

@router.message(Command("check"))
async def cmd_check(message: Message, bot: Bot):
    """Обработчик команды /check для ручного парсинга и отправки."""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return

    # Определяем режим проверки
    args = message.text.split()
    publish_to_channel = len(args) > 1 and args[1].lower() == "channel"

    status_msg = await message.answer("🔄 Запрашиваю данные от Epic Games API...")

    try:
        games = await epic_client.get_free_games()
        
        if not games:
            await status_msg.edit_text("ℹ️ В данный момент активных бесплатных раздач в API не найдено.")
            return

        target_chat_name = "канал" if publish_to_channel else "личные сообщения (превью)"
        await status_msg.edit_text(f"✅ Найдено раздач: {len(games)}. Начинаю отправку в {target_chat_name}...")

        target_chat_id = settings.channel_id if publish_to_channel else message.chat.id
        
        # Отправляем все игры одним постом (или альбомом)
        success = await publish_games(bot, target_chat_id, games)
        
        status_text = "Успешно отправлено" if success else "Ошибка при отправке"
        await message.answer(
            f"📊 *Результаты проверки:*\n"
            f"• Всего найдено игр: {len(games)}\n"
            f"• Статус публикации: {status_text}\n"
            f"• Куда: {'Канал' if publish_to_channel else 'ЛС (Превью)'}",
            parse_mode="Markdown"
        )
        
        # Удаляем временное статусное сообщение при успешном завершении
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
        except Exception:
            pass

    except Exception as e:
        logger.exception("Ошибка при выполнении ручной проверки /check: %s", str(e))
        try:
            await status_msg.edit_text(f"❌ Произошла ошибка во время проверки: {escape_markdown(str(e))}", parse_mode="MarkdownV2")
        except Exception:
            await message.answer(f"❌ Произошла ошибка во время проверки: {escape_markdown(str(e))}", parse_mode="MarkdownV2")

@router.message(Command("check_fab"))
async def cmd_check_fab(message: Message, bot: Bot):
    """Обработчик команды /check_fab для проверки раздач FAB."""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return

    # Определяем режим проверки
    args = message.text.split()
    publish_to_channel = len(args) > 1 and args[1].lower() == "channel"

    status_msg = await message.answer("🔄 Ищу информацию о раздачах FAB на Fab.com...")

    try:
        data = await fab_client.get_fab_freebies()
        
        if not data or not data.get("assets"):
            await status_msg.edit_text("ℹ️ В настоящее время бесплатных раздач на Fab.com не найдено.")
            return

        # Формируем текст сообщения
        header = (
            f"📦 *БЕСПЛАТНЫЙ КОНТЕНТ FAB* 📦\n\n"
            f"🔥 *Список бесплатных материалов на этот период:*\n\n"
        )
        
        body_parts = []
        for idx, asset in enumerate(data["assets"], start=1):
            asset_title = escape_markdown(asset["title"])
            asset_url = asset["url"].replace("(", "\\(").replace(")", "\\)")
            author = escape_markdown(asset.get("author", "Неизвестно"))
            
            desc = asset.get("description", "").strip()
            if desc:
                desc_esc = escape_markdown(desc)
                item_text = (
                    f"🔥 *{idx}\. [{asset_title}]({asset_url})*\n"
                    f"👤 Автор: *{author}*\n"
                    f"📖 _Описание: {desc_esc}_"
                )
            else:
                item_text = (
                    f"🔥 *{idx}\. [{asset_title}]({asset_url})*\n"
                    f"👤 Автор: *{author}*"
                )
            body_parts.append(item_text)
            
        body = "\n\n".join(body_parts)
        
        footer = (
            f"\n\n👉 Заберите их на странице [Fab Limited\-Time Free](https://www.fab.com/limited-time-free) "
            f"или в Unreal Engine Editor в разделе Fab\!"
        )
        
        text = f"{header}{body}{footer}"
        
        target_chat_id = settings.channel_id if publish_to_channel else message.chat.id
        
        await bot.send_message(
            chat_id=target_chat_id,
            text=text,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True
        )
        
        # Информируем админа
        await message.answer(
            f"📊 *Результаты проверки FAB:*\n"
            f"• Найдено ассетов: {len(data['assets'])}\n"
            f"• Куда отправлено: {'Канал' if publish_to_channel else 'ЛС (Превью)'}",
            parse_mode="Markdown"
        )
        
        # Удаляем временное сообщение
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
        except Exception:
            pass
            
    except Exception as e:
        logger.exception("Ошибка при выполнении ручной проверки /check_fab: %s", str(e))
        try:
            await status_msg.edit_text(f"❌ Произошла ошибка во время проверки FAB: {escape_markdown(str(e))}", parse_mode="MarkdownV2")
        except Exception:
            await message.answer(f"❌ Произошла ошибка во время проверки FAB: {escape_markdown(str(e))}", parse_mode="MarkdownV2")
