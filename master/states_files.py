import uuid
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
import database
from .helpers import (
    ADMIN_STATES, log_admin_action, get_readable_size, get_back_button
)
from .ui_files import show_folder_management, show_series_browse, show_manage_series

async def handle_files_states(client: Client, message: Message, state: str, state_data: dict, message_id: int) -> bool:
    user_id = message.from_user.id

    # Delegate bulk add and markers states
    from .states_files_bulk import handle_bulk_states
    if await handle_bulk_states(client, message, state, state_data, message_id):
        return True

    # 1. Waiting for File Upload
    if state == "waiting_for_file":
        media = message.document or message.video or message.audio or message.photo
        if not media:
            if message_id:
                try:
                    await client.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=message_id,
                        text="⚠️ Please send a valid file (document, video, audio, or photo).\n\n❌ Send /cancel to abort.",
                        reply_markup=InlineKeyboardMarkup([get_back_button("manage_files")])
                    )
                    return True
                except Exception:
                    pass
            return await message.reply_text("⚠️ Please send a valid file. Use /cancel to exit.")

        settings = await database.get_settings()
        db_channel = settings.get("db_channel_id")
        if not db_channel:
            ADMIN_STATES.pop(user_id, None)
            if message_id:
                try:
                    await client.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=message_id,
                        text="❌ Error: DB Storage Channel is not configured. Configure it in 'Database Sync & Integrity' menu first.",
                        reply_markup=InlineKeyboardMarkup([get_back_button("manage_files")])
                    )
                    return True
                except Exception:
                    pass
            return await message.reply_text("❌ Error: DB Storage Channel is not configured.")

        if message_id:
            try:
                await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text="⏳ **Processing and storing file... Please wait.**")
            except Exception:
                pass

        try:
            copied_msg = await message.copy(chat_id=int(db_channel) if db_channel.startswith("-100") or db_channel.isdigit() else db_channel)
            file_name = getattr(media, "file_name", "Photo" if message.photo else "Media File")
            file_size = getattr(media, "file_size", 0)
            mime_type = getattr(media, "mime_type", "image/jpeg" if message.photo else "unknown")
            caption = message.caption or ""
            file_code = str(uuid.uuid4())[:8]
            
            await database.add_file(
                file_code=file_code,
                message_id=copied_msg.id,
                file_name=file_name,
                file_size=file_size,
                mime_type=mime_type,
                caption=caption
            )

            primary = settings.get("primary_clone_username")
            link_str = f"https://t.me/{primary}?start=file_{file_code}" if primary else f"`file_{file_code}` (Activate a clone bot to get full link)"
            
            ADMIN_STATES.pop(user_id, None)
            text = f"✅ **File stored successfully!**\n\n" \
                   f"📂 **File Name:** `{file_name}`\n" \
                   f"📦 **Size:** {get_readable_size(file_size)}\n" \
                   f"🔗 **Shareable Link:** {link_str}"
            
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Files", callback_data="manage_files")]])
            if message_id:
                try:
                    await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=text, reply_markup=markup, disable_web_page_preview=True)
                    return True
                except Exception:
                    pass
            await message.reply_text(text, reply_markup=markup, disable_web_page_preview=True)
        except Exception as e:
            ADMIN_STATES.pop(user_id, None)
            error_text = f"❌ Failed to store file: {e}"
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Files", callback_data="manage_files")]])
            if message_id:
                try:
                    await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=error_text, reply_markup=markup)
                    return True
                except Exception:
                    pass
            await message.reply_text(error_text, reply_markup=markup)
        return True

    # 2. Waiting for Series Title
    elif state == "waiting_for_series_title":
        title = message.text.strip()
        ADMIN_STATES[user_id] = {
            "state": "waiting_for_series_desc",
            "message_id": message_id,
            "data": {"title": title}
        }
        text = f"🎬 Series Title set to: **{title}**\n\nNow send the **Series Description** (or send 'none' for empty):"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="manage_series")]])
        if message_id:
            try:
                await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=text, reply_markup=markup)
                return True
            except Exception:
                pass
        await message.reply_text(text, reply_markup=markup)
        return True

    # 3. Waiting for Series Description
    elif state == "waiting_for_series_desc":
        desc = message.text.strip()
        if desc.lower() == "none":
            desc = ""
        
        title = state_data["data"]["title"]
        series_id = await database.create_series(title, desc)
        ADMIN_STATES.pop(user_id, None)
        await log_admin_action(f"📂 **Series Created**: {title} (ID: {series_id}) by {message.from_user.mention}")
        
        if message_id:
            await show_manage_series(client, message.chat.id, message_id)
        else:
            await message.reply_text(f"✅ Series '{title}' created successfully!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Series Library", callback_data="manage_series")]]))
        return True

    # 4. Waiting for Tree Folder Name
    elif state == "waiting_for_tree_folder_name":
        name = message.text.strip()
        if not name:
            await message.reply_text("⚠️ Folder name cannot be empty. Try again or send /cancel.")
            return True
        
        series_id = state_data["data"]["series_id"]
        parent_folder_id = state_data["data"]["parent_folder_id"]
        parent_id = parent_folder_id if parent_folder_id > 0 else None
        
        await database.create_section(name, series_id, parent_id=parent_id, sec_type="folder")
        ADMIN_STATES.pop(user_id, None)
        
        if message_id:
            try:
                # show browse view
                await show_series_browse(client, message.chat.id, message_id, series_id, parent_folder_id if parent_folder_id > 0 else None)
                return True
            except Exception:
                pass
        await message.reply_text(f"✅ Folder '{name}' created successfully!")
        return True

    # 5. Waiting for Tree File Button Name
    elif state == "waiting_for_tree_file_btn_name":
        name = message.text.strip()
        if not name:
            await message.reply_text("⚠️ Button/File name cannot be empty. Try again or send /cancel.")
            return True

        series_id = state_data["data"]["series_id"]
        parent_folder_id = state_data["data"]["parent_folder_id"]
        parent_id = parent_folder_id if parent_folder_id > 0 else None
        
        new_sec_id = await database.create_section(name, series_id, parent_id=parent_id, sec_type="files")

        ADMIN_STATES[user_id]["state"] = "waiting_for_start_marker"
        ADMIN_STATES[user_id]["data"]["section_id"] = new_sec_id
        ADMIN_STATES[user_id]["data"]["file_name"] = name
        ADMIN_STATES[user_id]["data"]["is_new_section"] = True
        ADMIN_STATES[user_id]["data"]["clear_before"] = True

        text = (
            f"📥 **{name}** — Step 1: Start Marker\n\n"
            f"Please **forward the start message** from the source channel, or **paste the Telegram message link**:\n\n"
            "❌ Send `/cancel` to abort."
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]])
        
        if message_id:
            try:
                await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=text, reply_markup=markup)
                return True
            except Exception:
                pass
        await message.reply_text(text, reply_markup=markup)
        return True

    # 6. Waiting for Rename Folder / Section Name
    elif state == "waiting_for_rename_sec":
        new_name = message.text.strip()
        series_id = state_data["data"]["series_id"]
        section_id = state_data["data"]["section_id"]
        orig_msg_id = state_data.get("message_id")
        
        updated = await database.update_section(section_id, new_name)
        ADMIN_STATES.pop(user_id, None)
        
        if updated:
            if orig_msg_id:
                await show_folder_management(client, message.chat.id, orig_msg_id, series_id, section_id)
            else:
                await message.reply_text(f"✅ Renamed successfully to **{new_name}**!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"manage_folder_opt_{series_id}_{section_id}")]]))
        else:
            if orig_msg_id:
                await client.edit_message_text(chat_id=message.chat.id, message_id=orig_msg_id, text="❌ Failed to rename section.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"manage_folder_opt_{series_id}_{section_id}")]]))
            else:
                await message.reply_text("❌ Failed to rename section.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"manage_folder_opt_{series_id}_{section_id}")]]))
        return True

    # 7. Waiting for Folder Custom Message
    elif state == "waiting_for_folder_msg":
        new_msg = message.text.strip()
        series_id = state_data["data"]["series_id"]
        section_id = state_data["data"]["section_id"]
        
        if section_id == 0:
            await database.update_series_settings(series_id, custom_msg=new_msg)
        else:
            await database.update_section_settings(section_id, custom_msg=new_msg)
            
        ADMIN_STATES.pop(user_id, None)
        if message_id:
            await show_folder_management(client, message.chat.id, message_id, series_id, section_id)
        else:
            await message.reply_text("✅ Custom message updated successfully!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Management", callback_data=f"manage_folder_opt_{series_id}_{section_id}")]]))
        return True

    # 8. Waiting for Rename Series Title
    elif state == "waiting_for_rename_series":
        new_title = message.text.strip()
        series_id = state_data["data"]["series_id"]
        
        if not new_title:
            text = "⚠️ Title cannot be empty. Please send a valid title or send /cancel."
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"manage_folder_opt_{series_id}_0")]])
            if message_id:
                try:
                    await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=text, reply_markup=markup)
                    return True
                except Exception:
                    pass
            await message.reply_text(text, reply_markup=markup)
            return True
            
        await database.update_series_settings(series_id, title=new_title)
        ADMIN_STATES.pop(user_id, None)
        
        if message_id:
            await show_folder_management(client, message.chat.id, message_id, series_id, 0)
        else:
            await message.reply_text("✅ Series renamed successfully!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Management", callback_data=f"manage_folder_opt_{series_id}_0")]]))
        return True

    return False
