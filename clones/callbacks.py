from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import database
from .helpers import (
    check_user_subscribed, get_clone_welcome_markup,
    handle_auto_delete_if_enabled, log_download_action
)
from .tree import show_user_tree
from .handlers import handle_payload

async def clone_callback_handler(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
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
                dest_chat = int(db_channel) if db_channel.startswith("-100") or db_channel.isdigit() else db_channel
                sent_msg_ids = []
                for f in files:
                    try:
                        msg = await client.copy_message(chat_id=user_id, from_chat_id=dest_chat, message_id=f["message_id"])
                        sent_msg_ids.append(msg.id)
                    except Exception as e:
                        print(f"Failed to send {f['file_code']}: {e}")
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

        dest_chat = int(db_channel) if db_channel.startswith("-100") or db_channel.isdigit() else db_channel
        sent_msg_ids = []
        for f in files:
            try:
                msg = await client.copy_message(chat_id=user_id, from_chat_id=dest_chat, message_id=f["message_id"])
                sent_msg_ids.append(msg.id)
            except Exception as e:
                print(f"Failed to send file {f['file_code']}: {e}")
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

        await callback.answer("Delivering episode...")
        try:
            msg = await client.copy_message(
                chat_id=user_id,
                from_chat_id=int(db_channel) if db_channel.startswith("-100") or db_channel.isdigit() else db_channel,
                message_id=file_info["message_id"]
            )
            await handle_auto_delete_if_enabled(client, user_id, [msg.id])
            
            fake_msg = callback.message
            fake_msg.from_user = callback.from_user
            await log_download_action(client, file_info, fake_msg)
        except Exception as e:
            print(f"Failed to copy file message: {e}")
            await callback.message.reply_text("❌ Failed to deliver file. Please contact bot admin.")

    elif data.startswith("cl_browse_series_"):
        skip = int(data.split("_")[3])
        await callback.answer()
        
        series_list = await database.list_series()
        text = "🎬 **Browse Categories & Series**\n\nSelect a series to browse episodes:\n\n"
        buttons = []
        
        sliced_list = series_list[skip:skip+5]
        if not sliced_list:
            text += "_No series available._"
        else:
            for s in sliced_list:
                text += f"▪️ **{s['title']}**\n"
                buttons.append([InlineKeyboardButton(f"🎬 View {s['title'][:25]}", callback_data=f"cl_series_{s['id']}_0")])
        
        pag_row = []
        if skip > 0:
            pag_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"cl_browse_series_{max(0, skip - 5)}"))
        if skip + 5 < len(series_list):
            pag_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"cl_browse_series_{skip + 5}"))
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
