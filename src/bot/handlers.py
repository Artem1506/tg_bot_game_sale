import logging
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from src.config import settings
from src.api.epic_client import EpicGamesClient
from src.bot.publisher import publish_games, escape_markdown
from src.api.fab_client import FabClient
from src.bot.channels import ChannelsManager
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, JOIN_TRANSITION, LEAVE_TRANSITION
from aiogram.types import ChatMemberUpdated

logger = logging.getLogger(__name__)
router = Router()
epic_client = EpicGamesClient()
fab_client = FabClient()
channels_manager = ChannelsManager()

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
            "• `/check` — Проверить раздачи игр и прислать превью в текущий чат\.\n"
            "• `/check channel` — Опубликовать раздачи во все каналы и группы\.\n"
            "• `/check_fab` — Проверить раздачи FAB и прислать превью в текущий чат\.\n"
            "• `/check_fab channel` — Опубликовать раздачи FAB во все каналы и группы\.\n"
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
        "бесплатные раздачи игр в текущий чат в качестве *превью*.\n\n"
        "• `/check channel` — выполняет запрос к Epic Games API и *публикует* "
        "раздачи игр во все подключенные каналы и группы.\n\n"
        "• `/check_fab` — ищет информацию о раздачах напрямую на Fab.com и присылает список "
        "ассетов в текущий чат в качестве *превью*.\n\n"
        "• `/check_fab channel` — публикует список бесплатных ассетов FAB во все подключенные каналы и группы."
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

        if publish_to_channel:
            target_chats = set()
            if settings.channel_id:
                target_chats.add(settings.channel_id)
            for ch_id in channels_manager.get_channels().keys():
                try:
                    target_chats.add(int(ch_id))
                except ValueError:
                    target_chats.add(ch_id)
            
            await status_msg.edit_text(f"✅ Найдено раздач: {len(games)}. Публикую в {len(target_chats)} чатов/групп...")
            
            published_count = 0
            for chat_id in target_chats:
                try:
                    success = await publish_games(bot, chat_id, games)
                    if success:
                        published_count += 1
                except Exception as e:
                    logger.error("Ошибка при ручной публикации в чат %s: %s", chat_id, str(e))
            
            status_text = f"Успешно отправлено в {published_count} из {len(target_chats)} чатов/групп"
        else:
            await status_msg.edit_text(f"✅ Найдено раздач: {len(games)}. Начинаю отправку превью...")
            success = await publish_games(bot, message.chat.id, games)
            status_text = "Успешно отправлено" if success else "Ошибка при отправке"
            
        await message.answer(
            f"📊 *Результаты проверки:*\n"
            f"• Всего найдено игр: {len(games)}\n"
            f"• Статус публикации: {status_text}\n"
            f"• Куда: {'Каналы и группы' if publish_to_channel else 'Текущий чат (Превью)'}",
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
        
        if publish_to_channel:
            target_chats = set()
            if settings.channel_id:
                target_chats.add(settings.channel_id)
            for ch_id in channels_manager.get_channels().keys():
                try:
                    target_chats.add(int(ch_id))
                except ValueError:
                    target_chats.add(ch_id)
            
            await status_msg.edit_text(f"✅ Найдено ассетов FAB: {len(data['assets'])}. Публикую в {len(target_chats)} чатов/групп...")
            
            published_count = 0
            for chat_id in target_chats:
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode="MarkdownV2",
                        disable_web_page_preview=True
                    )
                    published_count += 1
                except Exception as e:
                    logger.error("Ошибка при ручной публикации FAB в чат %s: %s", chat_id, str(e))
                    
            status_text = f"Успешно отправлено в {published_count} из {len(target_chats)} чатов/групп"
        else:
            await status_msg.edit_text(f"✅ Найдено ассетов FAB: {len(data['assets'])}. Начинаю отправку превью...")
            await bot.send_message(
                chat_id=message.chat.id,
                text=text,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True
            )
            status_text = "Успешно отправлено"
            
        # Информируем админа
        await message.answer(
            f"📊 *Результаты проверки FAB:*\n"
            f"• Найдено ассетов: {len(data['assets'])}\n"
            f"• Статус публикации: {status_text}\n"
            f"• Куда отправлено: {'Каналы и группы' if publish_to_channel else 'Текущий чат (Превью)'}",
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

@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def on_bot_joined(event: ChatMemberUpdated):
    """Вызывается, когда бота добавляют в чат (канал/группу)."""
    chat = event.chat
    channels_manager.add_channel(chat.id, chat.title or "Без названия", chat.type)
    logger.info("Бот добавлен в чат: %s (ID: %s, тип: %s)", chat.title, chat.id, chat.type)

@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=LEAVE_TRANSITION))
async def on_bot_left(event: ChatMemberUpdated):
    """Вызывается, когда бота удаляют из чата (канала/группы)."""
    chat = event.chat
    channels_manager.remove_channel(chat.id)
    logger.info("Бот удален из чата: %s (ID: %s)", chat.title, chat.id)

@router.message(Command("dev_channels", "dev_chats"))
async def cmd_dev_channels(message: Message, bot: Bot):
    """Возвращает список всех каналов и чатов, куда добавлен бот. Доступно только разработчику."""
    if message.from_user.id != 1205125640:
        return  # Игнорируем запросы от других пользователей

    # Пытаемся опросить дефолтный канал из настроек, если его нет в списке
    default_channel_id = settings.channel_id
    if default_channel_id:
        try:
            chat = await bot.get_chat(default_channel_id)
            channels_manager.add_channel(chat.id, chat.title or "Без названия", chat.type)
        except Exception as e:
            logger.warning("Не удалось опросить дефолтный канал %s: %s", default_channel_id, str(e))

    channels = channels_manager.get_channels()
    
    if not channels:
        text = "📭 Список известных каналов пуст."
    else:
        text = "📢 *Список каналов и групп, куда добавлен бот:*\n\n"
        for idx, (ch_id, info) in enumerate(channels.items(), start=1):
            title = info.get("title", "Без названия")
            ch_type = info.get("type", "unknown")
            text += f"{idx}. *{title}*\n"
            text += f"   • ID: `{ch_id}`\n"
            text += f"   • Тип: `{ch_type}`\n\n"

    try:
        # Всегда отправляем в ЛС разработчику
        await bot.send_message(
            chat_id=1205125640,
            text=text,
            parse_mode="Markdown"
        )
        if message.chat.type != "private":
            await message.reply("Список каналов отправлен в личные сообщения.")
    except Exception as e:
        logger.exception("Ошибка при отправке списка каналов в ЛС: %s", str(e))
        # В случае неудачи (например, если ЛС заблокировано), пишем в чат вызова
        await message.reply(f"⚠️ Не удалось отправить в ЛС: {str(e)}\n\n{text}", parse_mode="Markdown")
