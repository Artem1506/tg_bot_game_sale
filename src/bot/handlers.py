import logging
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from src.config import settings
from src.api.epic_client import EpicGamesClient
from src.bot.publisher import publish_games, escape_markdown

logger = logging.getLogger(__name__)
router = Router()
epic_client = EpicGamesClient()

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
            "• `/check` — Проверить раздачи и прислать превью в это личное сообщение\.\n"
            "• `/check channel` — Проверить раздачи и принудительно опубликовать их в канал\.\n"
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
        "бесплатные раздачи в этот чат в качестве *превью* (в канал ничего не отправляется).\n\n"
        "• `/check channel` — выполняет запрос к Epic Games API и *принудительно публикует* "
        "все активные раздачи в Telegram-канал (даже если они уже публиковались и есть в истории)."
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
