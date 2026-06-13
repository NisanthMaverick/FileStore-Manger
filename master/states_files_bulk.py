import asyncio
import re
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
import database
from .helpers import (
    ADMIN_STATES, log_admin_action, parse_tg_link, extract_msg_from_forward
)
from .ui_files import show_series_browse
from .batch import copy_files_silently, run_batch_copy

def is_telegram_link(token: str) -> bool:
    token_lower = token.lower().strip()
    if "t.me/" in token_lower or token_lower.startswith("http://") or token_lower.startswith("https://"):
        return True
    return parse_tg_link(token) is not None

async def handle_bulk_states(client: Client, message: Message, state: str, state_data: dict, message_id: int) -> bool:
    user_id = message.from_user.id

    # 1. Waiting for Bulk Add text
    if state == "waiting_for_bulk_add":
        bulk_text = message.text.strip()
        if not bulk_text:
            await message.reply_text("⚠️ Content cannot be empty. Try again or send /cancel.")
            return True

        series_id = state_data["data"]["series_id"]
        section_id = state_data["data"]["section_id"]
        settings = await database.get_settings()
        db_channel = settings.get("db_channel_id")
        if not db_channel:
            if message_id:
                await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text="❌ DB Storage Channel is not configured.")
            else:
                await message.reply_text("❌ DB Storage Channel is not configured.")
            return True

        # Replace newlines with commas so we support both newline and comma separation
        bulk_text_commas = bulk_text.replace('\n', ',')
        raw_items = [item.strip().rstrip(',. ') for item in bulk_text_commas.split(',') if item.strip()]
        
        parsed_entries = []
        for item in raw_items:
            if not item:
                continue
            if item.startswith('"') and item.endswith('"'):
                folder_name = item[1:-1].strip()
                if folder_name:
                    parsed_entries.append({"type": "folder", "name": folder_name})
            else:
                parts = item.split()
                if len(parts) >= 2:
                    last_word = parts[-1]
                    sec_last_word = parts[-2]
                    
                    if is_telegram_link(last_word):
                        if is_telegram_link(sec_last_word):
                            end_link = last_word
                            start_link = sec_last_word
                            button_name = " ".join(parts[:-2]).strip()
                        else:
                            end_link = last_word
                            start_link = last_word
                            button_name = " ".join(parts[:-1]).strip()
                            
                        parsed_entries.append({
                            "type": "file",
                            "name": button_name,
                            "start_link": start_link,
                            "end_link": end_link
                        })

        if not parsed_entries:
            await message.reply_text(
                "⚠️ **No valid entries found.**\n\n"
                "Please enter items separated by commas or newlines:\n"
                "📁 Folder: `\"Folder Name\"`\n"
                "📥 File: `Button Name startLink endLink`\n\n"
                "Try again or send `/cancel`."
            )
            return True

        total_entries = len(parsed_entries)
        initial_text = f"⏳ **Creating buttons...**\n\nProgress: 0/{total_entries}"
        progress_msg = None
        
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Stop Creation", callback_data=f"stop_bulk_add_{series_id}_{section_id}")]])
        
        if message_id:
            try:
                progress_msg = await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=initial_text, reply_markup=reply_markup)
            except Exception:
                pass

        if not progress_msg:
            progress_msg = await message.reply_text(initial_text, reply_markup=reply_markup)

        ADMIN_STATES[user_id] = {
            "state": "bulk_adding",
            "message_id": progress_msg.id,
            "cancel_requested": False
        }

        parent_id = section_id if section_id > 0 else None
        status_lines = []
        completed = 0

        for entry in parsed_entries:
            if user_id in ADMIN_STATES and ADMIN_STATES[user_id].get("cancel_requested"):
                status_lines.append("🛑 **Creation stopped by admin.**")
                break
                
            if entry["type"] == "folder":
                name = entry["name"]
                try:
                    await database.create_section(name, series_id, parent_id=parent_id, sec_type="folder")
                    status_lines.append(f"📁 {name} Created")
                except Exception as e:
                    status_lines.append(f"❌ {name} (Error: {e})")
            elif entry["type"] == "file":
                name = entry["name"]
                start_link = entry["start_link"]
                end_link = entry["end_link"]

                start_info = parse_tg_link(start_link)
                end_info = parse_tg_link(end_link)

                if not start_info or not end_info:
                    status_lines.append(f"❌ {name} (Invalid links)")
                elif start_info[0] != end_info[0]:
                    status_lines.append(f"❌ {name} (Links from different chats)")
                elif end_info[1] < start_info[1]:
                    status_lines.append(f"❌ {name} (End link is before start link)")
                else:
                    try:
                        new_sec_id = await database.create_section(name, series_id, parent_id=parent_id, sec_type="files")
                        await copy_files_silently(client, db_channel, start_info[0], start_info[1], end_info[1], series_id, new_sec_id, name)
                        status_lines.append(f"✅ {name}")
                    except Exception as e:
                        status_lines.append(f"❌ {name} (Copy error: {e})")

            completed += 1
            display_lines = status_lines[-10:]
            progress_text = f"⏳ **Creating buttons...**\n\n" + "\n".join(display_lines) + f"\n\nProgress: {completed}/{total_entries}"
            try:
                await client.edit_message_text(chat_id=message.chat.id, message_id=progress_msg.id, text=progress_text, reply_markup=reply_markup)
            except Exception:
                pass
            await asyncio.sleep(0.2)

        ADMIN_STATES.pop(user_id, None)

        final_lines = status_lines
        if len(final_lines) > 20:
            final_lines = final_lines[:10] + ["..."] + final_lines[-10:]
            
        is_stopped = any("stopped" in line.lower() for line in status_lines)
        if is_stopped:
            success_text = f"🛑 **Bulk creation stopped!**\n\n" + "\n".join(final_lines) + f"\n\nProgress: {completed}/{total_entries}"
        else:
            success_text = f"✅ **Bulk creation completed successfully!**\n\n" + "\n".join(final_lines) + f"\n\nProgress: {total_entries}/{total_entries}"
            
        try:
            await client.edit_message_text(chat_id=message.chat.id, message_id=progress_msg.id, text=success_text)
        except Exception:
            pass

        await asyncio.sleep(2)
        await show_series_browse(client, message.chat.id, progress_msg.id, series_id, section_id if section_id > 0 else None)
        return True

    # 2. Waiting for Tree Start Marker
    elif state == "waiting_for_start_marker":
        chat_id, msg_id = None, None
        forward_info = extract_msg_from_forward(message)
        if forward_info:
            chat_id, msg_id = forward_info
        elif message.text:
            link_info = parse_tg_link(message.text)
            if link_info:
                chat_id, msg_id = link_info
        
        series_id = state_data["data"]["series_id"]
        section_id = state_data["data"]["section_id"]
        
        if not chat_id or not msg_id:
            await message.reply_text("❌ Invalid marker. Forward a message or paste a Telegram link.\n\n❌ Send `/cancel` to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]]))
            return True
        
        ADMIN_STATES[user_id]["state"] = "waiting_for_end_marker"
        ADMIN_STATES[user_id]["data"]["start_chat_id"] = chat_id
        ADMIN_STATES[user_id]["data"]["start_msg_id"] = msg_id
        
        text = (
            "📤 **Add Files - Step 2: End Marker**\n\n"
            f"Start Marker: Chat `{chat_id}` / Message `{msg_id}`\n\n"
            "Please **forward the end message** from the SAME channel, or **paste its Telegram message link**:\n\n"
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

    # 3. Waiting for Tree End Marker
    elif state == "waiting_for_end_marker":
        chat_id, msg_id = None, None
        forward_info = extract_msg_from_forward(message)
        if forward_info:
            chat_id, msg_id = forward_info
        elif message.text:
            link_info = parse_tg_link(message.text)
            if link_info:
                chat_id, msg_id = link_info
        
        series_id = state_data["data"]["series_id"]
        section_id = state_data["data"]["section_id"]
        start_chat_id = state_data["data"]["start_chat_id"]
        start_msg_id = state_data["data"]["start_msg_id"]
        
        if not chat_id or not msg_id:
            await message.reply_text("❌ Invalid marker. Forward a message or paste a Telegram link.\n\n❌ Send `/cancel` to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]]))
            return True
        
        if chat_id != start_chat_id:
            await message.reply_text("❌ End marker must be from the same chat. Try again.\n\n❌ Send `/cancel` to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]]))
            return True
        
        if msg_id < start_msg_id:
            await message.reply_text("❌ End message ID must be >= start message ID. Try again.\n\n❌ Send `/cancel` to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]]))
            return True
        
        ADMIN_STATES.pop(user_id, None)
        parent_folder_id = state_data["data"].get("parent_folder_id")
        redirect_id = parent_folder_id if parent_folder_id is not None else section_id
        orig_msg_id = state_data.get("message_id")

        clear_before = state_data["data"].get("clear_before", True)
        custom_file_name = state_data["data"].get("file_name")
        if orig_msg_id:
            try:
                await client.edit_message_text(chat_id=message.chat.id, message_id=orig_msg_id, text=f"⏳ **Importing files...**\nSource: `{chat_id}` │ Range: `{start_msg_id}` → `{msg_id}`")
            except Exception:
                pass
        asyncio.create_task(run_batch_copy(client, message.chat.id, orig_msg_id, chat_id, start_msg_id, msg_id, series_id, section_id, redirect_folder_id=redirect_id, clear_before=clear_before, custom_file_name=custom_file_name))
        return True

    return False
