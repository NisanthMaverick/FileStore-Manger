from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
import database
from .helpers import (
    log_new_user_start, check_user_subscribed, get_clone_welcome_markup,
    handle_auto_delete_if_enabled, log_download_action,
    copy_messages_with_start_end
)
from .tree import show_user_tree

async def clone_start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username
    bot_me = client.me

    is_new = await database.add_user(user_id, username, first_name)
    if is_new:
        await log_new_user_start(client, message)

    payload = message.text.split(" ", 1)[1] if len(message.text.split(" ", 1)) > 1 else ""

    is_subbed, invite_buttons = await check_user_subscribed(client, user_id)
    if not is_subbed:
        buttons = []
        for btn in invite_buttons:
            buttons.append([InlineKeyboardButton(btn["text"], url=btn["url"])])
        
        ref_data = f"fsub_ref_{payload}" if payload else "fsub_ref_home"
        buttons.append([InlineKeyboardButton("🔄 Refresh", callback_data=ref_data)])
        
        return await message.reply_text(
            f"Hey {message.from_user.mention} ʏᴏᴜ ɴᴇᴇᴅ ᴊᴏɪɴ Oᴜʀ ᴄʜᴀɴɴᴇʟ ɪɴ ᴏʀᴅᴇʀ ᴛᴏ ᴜsᴇ ᴍᴇ 😉\n\n"
            "__Pʀᴇss ᴛʜᴇ Fᴏʟʟᴏᴡɪɴɢ Bᴜᴛᴛᴏɴ ᴛᴏ ᴊᴏɪɴ Nᴏᴡ 👇__",
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True
        )

    await handle_payload(client, message, payload)

async def clone_id_handler(client: Client, message: Message):
    user_id = message.from_user.id
    await message.reply_text(f"🆔 **Your Telegram ID:** `{user_id}`")

async def clone_explore_handler(client: Client, message: Message):
    series_list = await database.list_series()
    text = "🎬 **Browse Categories & Series**\n\nSelect a series to browse:\n\n"
    buttons = []
    
    sliced_list = series_list[0:5]
    if not sliced_list:
        text += "_No series available._"
    else:
        for s in sliced_list:
            text += f"▪️ **{s['title']}**\n"
            buttons.append([InlineKeyboardButton(f"🎬 View {s['title'][:25]}", callback_data=f"cl_series_{s['id']}_0")])
    
    pag_row = []
    if len(series_list) > 5:
        pag_row.append(InlineKeyboardButton("Next ➡️", callback_data="cl_browse_series_5"))
    if pag_row:
        buttons.append(pag_row)
        
    buttons.append([InlineKeyboardButton("🔙 Back Home", callback_data="cl_welcome_home")])
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def handle_payload(client: Client, message: Message, payload: str):
    user_id = message.from_user.id
    settings = await database.get_settings()

    if not payload:
        welcome_text = settings.get("welcome_msg") or "Hey {mention}, welcome to {bot_name}!"
        bot_me = client.me
        welcome_text = welcome_text.format(
            mention=message.from_user.mention,
            first_name=message.from_user.first_name,
            bot_name=bot_me.first_name,
            bot_link=f"https://t.me/{bot_me.username}",
            mention_bot=f"[{bot_me.first_name}](tg://user?id={bot_me.id})",
            mentionbot=f"[{bot_me.first_name}](tg://user?id={bot_me.id})"
        )
        markup = get_clone_welcome_markup(settings.get("custom_buttons", "[]"))
        
        full_markup = []
        if markup:
            full_markup = list(markup.inline_keyboard)
        full_markup.append([InlineKeyboardButton("🎬 Browse Series / Categories", callback_data="cl_browse_series_0")])
        
        await message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(full_markup))

    elif payload.startswith("file_"):
        file_code = payload.replace("file_", "")
        file_info = await database.get_file(file_code)
        
        if not file_info:
            return await message.reply_text("❌ File not found or has been deleted by administration.")

        db_channel = settings.get("db_channel_id")
        if not db_channel:
            return await message.reply_text("❌ System configuration issue: storage channel not set. Please contact admin.")

        status_msg = await message.reply_text("🔄 Retrieving file from database...")
        try:
            sent_msg_ids = await copy_messages_with_start_end(client, user_id, db_channel, [file_info["message_id"]])
            await status_msg.delete()
            if sent_msg_ids:
                await handle_auto_delete_if_enabled(client, user_id, sent_msg_ids)
            await log_download_action(client, file_info, message)
        except Exception as e:
            print(f"Failed to copy file message: {e}")
            try:
                await status_msg.edit_text("❌ Failed to deliver file. Please contact bot admin.")
            except Exception:
                pass

    elif payload.startswith("series_"):
        try:
            series_id = int(payload.replace("series_", ""))
        except ValueError:
            return await message.reply_text("❌ Invalid Series Link.")

        await show_user_tree(client, message.chat.id, None, series_id, section_id=None, is_new_message=True)
