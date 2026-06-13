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

        # Pre-process: merge lines that have '+' at the boundary
        lines = bulk_text.split('\n')
        merged_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if merged_lines and (merged_lines[-1].endswith('+') or line.startswith('+')):
                merged_lines[-1] = (merged_lines[-1] + " " + line).strip()
            else:
                merged_lines.append(line)
        processed_text = "\n".join(merged_lines)

        # Replace newlines with commas so we support both newline and comma separation
        bulk_text_commas = processed_text.replace('\n', ',')
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
                sub_parts = [part.strip() for part in item.split('+') if part.strip()]
                if not sub_parts:
                    continue
                
                first_part = sub_parts[0]
                first_words = [w.replace('(', '').replace(')', '').strip() for w in first_part.split()]
                first_words = [w for w in first_words if w]
                if len(first_words) >= 2:
                    last_word = first_words[-1]
                    sec_last_word = first_words[-2]
                    
                    if is_telegram_link(last_word):
                        if is_telegram_link(sec_last_word):
                            end_link = last_word
                            start_link = sec_last_word
                            button_name = " ".join(first_words[:-2]).strip()
                        else:
                            end_link = last_word
                            start_link = last_word
                            button_name = " ".join(first_words[:-1]).strip()
                            
                        ranges = [{"start_link": start_link, "end_link": end_link}]
                        
                        valid = True
                        for part in sub_parts[1:]:
                            part_words = [w.replace('(', '').replace(')', '').strip() for w in part.split()]
                            part_words = [w for w in part_words if w]
                            if not part_words:
                                continue
                            if len(part_words) >= 2 and is_telegram_link(part_words[-1]) and is_telegram_link(part_words[-2]):
                                ranges.append({
                                    "start_link": part_words[-2],
                                    "end_link": part_words[-1]
                                })
                            elif len(part_words) >= 1 and is_telegram_link(part_words[-1]):
                                ranges.append({
                                    "start_link": part_words[-1],
                                    "end_link": part_words[-1]
                                })
                            else:
                                valid = False
                                break
                        
                        if valid:
                            parsed_entries.append({
                                "type": "file",
                                "name": button_name,
                                "ranges": ranges
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
                ranges = entry["ranges"]

                # Validate all ranges first
                validated_ranges = []
                has_error = False
                error_msg = ""

                for r in ranges:
                    start_link = r["start_link"]
                    end_link = r["end_link"]
                    start_info = parse_tg_link(start_link)
                    end_info = parse_tg_link(end_link)

                    if not start_info or not end_info:
                        has_error = True
                        error_msg = "Invalid links"
                        break
                    elif start_info[0] != end_info[0]:
                        has_error = True
                        error_msg = "Links from different chats"
                        break
                    elif end_info[1] < start_info[1]:
                        has_error = True
                        error_msg = "End link is before start link"
                        break
                    else:
                        validated_ranges.append((start_info[0], start_info[1], end_info[1]))

                if has_error:
                    status_lines.append(f"❌ {name} ({error_msg})")
                else:
                    try:
                        new_sec_id = await database.create_section(name, series_id, parent_id=parent_id, sec_type="files")
                        for source_chat_id, start_msg_id, end_msg_id in validated_ranges:
                            await copy_files_silently(client, db_channel, source_chat_id, start_msg_id, end_msg_id, series_id, new_sec_id, name)
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

    # 2. Waiting for Tree File Links (replacing start/end marker)
    elif state == "waiting_for_tree_file_links":
        ranges = []
        forward_info = extract_msg_from_forward(message)
        if forward_info:
            chat_id, msg_id = forward_info
            ranges.append({
                "chat_id": chat_id,
                "start_id": msg_id,
                "end_id": msg_id
            })
        elif message.text:
            text = message.text.strip()
            # Split by '+'
            parts = [p.strip() for p in text.split('+') if p.strip()]
            if not parts:
                await message.reply_text("❌ Input cannot be empty. Try again or send /cancel.")
                return True
                
            for part in parts:
                tokens = [w.replace('(', '').replace(')', '').strip() for w in part.split()]
                tokens = [w for w in tokens if w]
                if not tokens:
                    continue
                if len(tokens) >= 2:
                    t1, t2 = tokens[0], tokens[1]
                    info1 = parse_tg_link(t1)
                    info2 = parse_tg_link(t2)
                    if not info1 or not info2:
                        await message.reply_text(f"❌ Invalid links: `{t1}` or `{t2}`. Ensure they are valid Telegram message links.\n\n❌ Send `/cancel` to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]]))
                        return True
                    if info1[0] != info2[0]:
                        await message.reply_text(f"❌ Links must be from the same chat:\n`{t1}`\n`{t2}`\n\n❌ Send `/cancel` to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]]))
                        return True
                    if info2[1] < info1[1]:
                        await message.reply_text(f"❌ End link message ID must be >= start link ID in:\n`{t1} {t2}`\n\n❌ Send `/cancel` to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]]))
                        return True
                    ranges.append({
                        "chat_id": info1[0],
                        "start_id": info1[1],
                        "end_id": info2[1]
                    })
                elif len(tokens) == 1:
                    t1 = tokens[0]
                    info1 = parse_tg_link(t1)
                    if not info1:
                        await message.reply_text(f"❌ Invalid link: `{t1}`.\n\n❌ Send `/cancel` to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]]))
                        return True
                    ranges.append({
                        "chat_id": info1[0],
                        "start_id": info1[1],
                        "end_id": info1[1]
                    })
                else:
                    await message.reply_text("❌ Invalid format. Use `link` or `startLink endLink`.\n\n❌ Send `/cancel` to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]]))
                    return True
        else:
            await message.reply_text("❌ Invalid input type. Forward a message or send Telegram link(s).\n\n❌ Send `/cancel` to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]]))
            return True

        if not ranges:
            await message.reply_text("❌ No valid links found. Try again or send /cancel.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]]))
            return True

        series_id = state_data["data"]["series_id"]
        section_id = state_data["data"]["section_id"]
        parent_folder_id = state_data["data"].get("parent_folder_id")
        redirect_id = parent_folder_id if parent_folder_id is not None else section_id
        orig_msg_id = state_data.get("message_id")
        clear_before = state_data["data"].get("clear_before", True)
        custom_file_name = state_data["data"].get("file_name")
        library_skip = state_data["data"].get("library_skip", 0)

        ADMIN_STATES.pop(user_id, None)

        if orig_msg_id:
            try:
                await client.edit_message_text(chat_id=message.chat.id, message_id=orig_msg_id, text=f"⏳ **Importing files...**\nProcessing ranges/links...")
            except Exception:
                pass
        
        from .batch import run_multi_range_copy
        asyncio.create_task(run_multi_range_copy(
            client=client,
            admin_chat_id=message.chat.id,
            progress_message_id=orig_msg_id,
            ranges=ranges,
            series_id=series_id,
            section_id=section_id,
            redirect_folder_id=redirect_id,
            clear_before=clear_before,
            custom_file_name=custom_file_name,
            library_skip=library_skip
        ))
        return True

    return False
