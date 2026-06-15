from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import database
from .helpers import (
    check_user_subscribed, get_clone_welcome_markup,
    handle_auto_delete_if_enabled, log_download_action,
    copy_messages_with_start_end, check_clone_access, handle_clone_callback_access_denied,
    SENDING_USERS
)
from .tree import show_user_tree
from .handlers import handle_payload
from config import OWNER_ID

async def clone_callback_handler(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in SENDING_USERS:
        return await callback.answer("⚠️ Your series is sending. Once complete all files, try a new file.", show_alert=True)
    if not await check_clone_access(user_id):
        await handle_clone_callback_access_denied(client, callback)
        return
    data = callback.data

    if data.startswith("fsub_ref_"):
        is_subbed, invite_buttons = await check_user_subscribed(client, user_id)
        if not is_subbed:
            return await callback.answer("Yᴏᴜ ᴀʀᴇ ɴᴏᴛ ʏᴇᴛ ᴊᴏɪɴᴇᴅ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ. \nFɪʀsᴛ ᴊᴏɪɴ ᴀɴᴅ ᴛʜᴇɴ ᴘʀᴇss ʀᴇғʀᴇsʜ ʙᴜᴛᴛᴏɴ 🤤", show_alert=True)

        payload = data.replace("fsub_ref_", "")
        if payload == "home":
            payload = ""

        await callback.answer("Verification successful! Delivering...")
        await callback.message.delete()
        
        fake_message = callback.message
        fake_message.from_user = callback.from_user
        await handle_payload(client, fake_message, payload)

    elif data.startswith("cl_series_"):
        series_id = int(data.split("_")[2])
        series = await database.get_series(series_id)
        if series and not series.get("is_active", True):
            is_user_premium = False
            if await database.is_admin(user_id, OWNER_ID) or await database.is_subscriber(user_id):
                is_user_premium = True
            
            if not is_user_premium:
                await callback.answer("🔒 This series is restricted to premium users.", show_alert=True)
                owner_username = None
                try:
                    owner_user = await client.get_users(OWNER_ID)
                    if owner_user and owner_user.username:
                        owner_username = owner_user.username
                except Exception:
                    pass
                contact_url = f"https://t.me/{owner_username}" if owner_username else f"tg://user?id={OWNER_ID}"
                
                text = (
                    "🔒 **Premium Access Required**\n\n"
                    "You are not a premium user to see old series/content.\n"
                    "If you want old series, please contact the administrator."
                )
                markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("👨‍💻 Contact Admin", url=contact_url)],
                    [InlineKeyboardButton("🔙 Back to Series Library", callback_data="cl_browse_series_0")]
                ])
                await callback.message.edit_text(text, reply_markup=markup)
                return

        await callback.answer()
        await show_user_tree(client, callback.message.chat.id, callback.message.id, series_id, section_id=None)

    elif data.startswith("cl_tree_"):
        parts = data.split("_")
        series_id = int(parts[2])
        section_id = int(parts[3])

        if section_id > 0:
            sec = await database.get_section(section_id)
            if sec and sec.get("sec_type") == "files":
                settings = await database.get_settings()
                db_channel = settings.get("db_channel_id")
                if not db_channel:
                    return await callback.answer("Storage channel not configured.", show_alert=True)
                files, total_files = await database.list_files(skip=0, limit=500, series_id=series_id, section_id=section_id)
                if not files:
                    return await callback.answer("No files in this section yet.", show_alert=True)
                await callback.answer(f"⏳ Sending {total_files} file(s)...")
                
                file_msg_ids = [f["message_id"] for f in files]
                sent_msg_ids = await copy_messages_with_start_end(client, user_id, db_channel, file_msg_ids)
                
                if sent_msg_ids:
                    await handle_auto_delete_if_enabled(client, user_id, sent_msg_ids)
                return

        await callback.answer()
        await show_user_tree(client, callback.message.chat.id, callback.message.id, series_id, section_id=section_id if section_id > 0 else None)

    elif data.startswith("cl_send_sec_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])

        settings = await database.get_settings()
        db_channel = settings.get("db_channel_id")
        if not db_channel:
            return await callback.answer("Storage channel not configured.", show_alert=True)

        files, total_files = await database.list_files(skip=0, limit=500, series_id=series_id, section_id=section_id)
        if not files:
            return await callback.answer("No files found in this section.", show_alert=True)

        await callback.answer(f"⏳ Sending {total_files} file(s)...")

        file_msg_ids = [f["message_id"] for f in files]
        sent_msg_ids = await copy_messages_with_start_end(client, user_id, db_channel, file_msg_ids)
        
        if sent_msg_ids:
            await handle_auto_delete_if_enabled(client, user_id, sent_msg_ids)

        try:
            fake_msg = callback.message
            fake_msg.from_user = callback.from_user
            await log_download_action(client, files[0], fake_msg)
        except Exception:
            pass

    elif data.startswith("get_ep_"):
        file_code = data.split("_")[2]
        file_info = await database.get_file(file_code)
        if not file_info:
            return await callback.answer("File not found or deleted.", show_alert=True)

        settings = await database.get_settings()
        db_channel = settings.get("db_channel_id")
        if not db_channel:
            return await callback.answer("Storage channel not configured by admin.", show_alert=True)

        if settings.get("lock_buttons_enabled"):
            is_user_premium = False
            if await database.is_admin(user_id, OWNER_ID) or await database.is_subscriber(user_id):
                is_user_premium = True
            
            if not is_user_premium:
                # Check if parent series is active. If inactive, it's locked.
                parent_series_active = True
                if file_info.get("series_id"):
                    series = await database.get_series(file_info["series_id"])
                    if series and not series.get("is_active", True):
                        parent_series_active = False
                
                if not parent_series_active:
                    return await callback.answer("🔒 This series is restricted to premium users.", show_alert=True)

                window = settings.get("lock_time_window", 0)
                is_within_window = False
                if file_info.get("section_id"):
                    sec = await database.get_section(file_info["section_id"])
                    if sec and window > 0 and sec.get("created_at"):
                        from datetime import datetime
                        age_hours = (datetime.utcnow() - sec["created_at"]).total_seconds() / 3600.0
                        if age_hours < window:
                            is_within_window = True
                
                if not is_within_window:
                    files, total = await database.list_files(skip=0, limit=1000, series_id=file_info.get("series_id"), section_id=file_info.get("section_id"))
                    if files:
                        latest_file = max(files, key=lambda f: f["message_id"])
                        if file_info["file_code"] != latest_file["file_code"]:
                            return await callback.answer("🔒 You are not a premium user, only premium users can access old files.", show_alert=True)

        await callback.answer("Delivering episode...")
        try:
            sent_msg_ids = await copy_messages_with_start_end(client, user_id, db_channel, [file_info["message_id"]])
            if sent_msg_ids:
                await handle_auto_delete_if_enabled(client, user_id, sent_msg_ids)
            
            fake_msg = callback.message
            fake_msg.from_user = callback.from_user
            await log_download_action(client, file_info, fake_msg)
        except Exception as e:
            print(f"Failed to copy file message: {e}")
            await callback.message.reply_text("❌ Failed to deliver file. Please contact bot admin.")

    elif data.startswith("cl_browse_series_"):
        skip = int(data.split("_")[3])
        await callback.answer()
        
        settings = await database.get_settings()
        limit = settings.get("series_buttons_per_page", 5)
        library_msg = settings.get("series_library_custom_msg")
        
        series_list = await database.list_series()
        
        header = "🎬 **Browse Categories & Series**\n\nSelect a series to browse episodes:\n\n"
        if library_msg:
            text = f"{library_msg}\n\n{header}"
        else:
            text = header
            
        buttons = []
        
        is_user_premium = False
        if await database.is_admin(user_id, OWNER_ID) or await database.is_subscriber(user_id):
            is_user_premium = True

        sliced_list = series_list[skip:skip+limit]
        if not sliced_list:
            text += "_No series available._"
        else:
            for s in sliced_list:
                text += f"▪️ **{s['title']}**\n"
                is_series_unlocked = s.get("is_active", True) or is_user_premium
                if is_series_unlocked:
                    buttons.append([InlineKeyboardButton(f"🎬 {s['title']}", callback_data=f"cl_series_{s['id']}_0")])
                else:
                    buttons.append([InlineKeyboardButton(f"🔒 {s['title']}", callback_data=f"cl_series_{s['id']}_0")])
        
        pag_row = []
        if skip > 0:
            pag_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"cl_browse_series_{max(0, skip - limit)}"))
        if skip + limit < len(series_list):
            pag_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"cl_browse_series_{skip + limit}"))
        if pag_row:
            buttons.append(pag_row)
            
        buttons.append([InlineKeyboardButton("🔙 Back Home", callback_data="cl_welcome_home")])
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "cl_welcome_home":
        await callback.answer()
        settings = await database.get_settings()
        welcome_text = settings.get("welcome_msg") or "Hey {mention}, welcome to {bot_name}!"
        welcome_text = welcome_text.format(
            mention=callback.from_user.mention,
            first_name=callback.from_user.first_name,
            bot_name=client.me.first_name,
            bot_link=f"https://t.me/{client.me.username}",
            mention_bot=f"[{client.me.first_name}](tg://user?id={client.me.id})",
            mentionbot=f"[{client.me.first_name}](tg://user?id={client.me.id})"
        )
        markup = get_clone_welcome_markup(settings.get("custom_buttons", "[]"))
        
        full_markup = []
        if markup:
            full_markup = list(markup.inline_keyboard)
        full_markup.append([InlineKeyboardButton("🎬 Browse Series / Categories", callback_data="cl_browse_series_0")])
        
        await callback.message.edit_text(welcome_text, reply_markup=InlineKeyboardMarkup(full_markup))

    elif data.startswith("cl_locked_sec_"):
        await callback.answer("🔒 You are not a premium user, only premium users can access old files.", show_alert=True)
