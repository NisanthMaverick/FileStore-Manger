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

def clean_link_token(token: str) -> str:
    cleaned = token.strip()
    while cleaned and cleaned[0] in ('(', '[', '{', '"', "'"):
        cleaned = cleaned[1:]
    while cleaned and cleaned[-1] in (')', ']', '}', '"', "'", ',', '.', ';', ':'):
        cleaned = cleaned[:-1]
    return cleaned.strip()

def is_telegram_link(token: str) -> bool:
    token_lower = token.lower().strip()
    if "t.me/" in token_lower or token_lower.startswith("http://") or token_lower.startswith("https://"):
        return True
    return parse_tg_link(token) is not None

def split_top_level(text: str) -> list[str]:
    parts = []
    current = []
    depth = 0
    in_quotes = False
    
    bracket_map = {'{': '}', '[': ']', '(': ')'}
    inverse_brackets = {'}': '{', ']': '[', ')': '('}
    stack = []
    
    for char in text:
        if char == '"':
            in_quotes = not in_quotes
            current.append(char)
        elif in_quotes:
            current.append(char)
        elif char in bracket_map:
            depth += 1
            stack.append(char)
            current.append(char)
        elif char in inverse_brackets:
            if stack and stack[-1] == inverse_brackets[char]:
                stack.pop()
                depth -= 1
            current.append(char)
        elif depth == 0 and char in (',', '\n'):
            segment = "".join(current).strip()
            if segment:
                parts.append(segment)
            current = []
        else:
            current.append(char)
            
    segment = "".join(current).strip()
    if segment:
        parts.append(segment)
        
    return parts

def parse_bulk_segment(segment: str) -> dict | None:
    segment = segment.strip()
    if not segment:
        return None
        
    # Check if this segment represents a folder: starts with '[' and ends with ']'
    # e.g., ["Folder Name"{ contents }]
    if segment.startswith('[') and segment.endswith(']'):
        first_bracket = segment.find('[')
        first_brace = segment.find('{')
        last_brace = segment.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            name_part = segment[first_bracket + 1:first_brace].strip()
            # Strip quotes if any
            if name_part.startswith('"') and name_part.endswith('"'):
                folder_name = name_part[1:-1].strip()
            elif name_part.startswith("'") and name_part.endswith("'"):
                folder_name = name_part[1:-1].strip()
            else:
                folder_name = name_part.strip()
                
            contents = segment[first_brace + 1:last_brace].strip()
            children = parse_bulk_hierarchy(contents)
            return {
                "type": "folder",
                "name": folder_name,
                "children": children
            }
            
    # File button parser
    segment_words = segment.split()
    has_link = any(is_telegram_link(clean_link_token(w)) for w in segment_words)
    if has_link:
        sub_parts = [sp.strip() for sp in segment.split('+') if sp.strip()]
        if not sub_parts:
            return None
            
        first_part = sub_parts[0]
        first_words = first_part.split()
        if len(first_words) >= 1:
            last_word = clean_link_token(first_words[-1])
            sec_last_word = clean_link_token(first_words[-2]) if len(first_words) >= 2 else None
            
            if is_telegram_link(last_word):
                if sec_last_word and is_telegram_link(sec_last_word):
                    end_link = last_word
                    start_link = sec_last_word
                    button_name = " ".join(first_words[:-2]).strip()
                else:
                    end_link = last_word
                    start_link = last_word
                    button_name = " ".join(first_words[:-1]).strip()
                    
                ranges = [{"start_link": start_link, "end_link": end_link}]
                
                valid = True
                for spart in sub_parts[1:]:
                    spart_clean = spart.strip()
                    if spart_clean.startswith('(') and spart_clean.endswith(')'):
                        spart_clean = spart_clean[1:-1].strip()
                    spart_words = [clean_link_token(w) for w in spart_clean.split() if w]
                    if not spart_words:
                        continue
                    if len(spart_words) >= 2 and is_telegram_link(spart_words[-1]) and is_telegram_link(spart_words[-2]):
                        ranges.append({
                            "start_link": spart_words[-2],
                            "end_link": spart_words[-1]
                        })
                    elif len(spart_words) >= 1 and is_telegram_link(spart_words[-1]):
                        ranges.append({
                            "start_link": spart_words[-1],
                            "end_link": spart_words[-1]
                        })
                    else:
                        valid = False
                        break
                        
                if valid:
                    return {
                        "type": "file",
                        "name": button_name,
                        "ranges": ranges
                    }
    return None

def parse_bulk_hierarchy(text: str) -> list[dict]:
    # Pre-process lines: strip comments and merge '+' lines
    lines = text.split('\n')
    processed_lines = []
    for line in lines:
        if '#' in line:
            line = line.split('#', 1)[0]
        processed_lines.append(line.strip())
        
    merged_lines = []
    for line in processed_lines:
        if not line:
            continue
        if merged_lines and (merged_lines[-1].endswith('+') or line.startswith('+')):
            merged_lines[-1] = (merged_lines[-1] + " " + line).strip()
        else:
            merged_lines.append(line)
            
    cleaned_text = "\n".join(merged_lines).strip()
    
    segments = split_top_level(cleaned_text)
    parsed_entries = []
    for seg in segments:
        parsed = parse_bulk_segment(seg)
        if parsed:
            parsed_entries.append(parsed)
    return parsed_entries

def count_nodes(nodes):
    total = 0
    for node in nodes:
        total += 1
        if node["type"] == "folder" and "children" in node:
            total += count_nodes(node["children"])
    return total

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
        db_channel = None
        if series_id:
            series = await database.get_series(series_id)
            if series and series.get("journey_id"):
                journey = await database.get_journey(series["journey_id"])
                if journey and journey.get("db_channel_id"):
                    db_channel = journey["db_channel_id"]

        settings = await database.get_settings()
        if not db_channel:
            db_channel = settings.get("db_channel_id")

        if not db_channel:
            if message_id:
                await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text="❌ DB Storage Channel is not configured.")
            else:
                await message.reply_text("❌ DB Storage Channel is not configured.")
            return True

        parsed_entries = parse_bulk_hierarchy(bulk_text)

        if not parsed_entries:
            await message.reply_text(
                "⚠️ **No valid entries found.**\n\n"
                "Please verify your layout format and make sure there are no typos.\n\n"
                "📁 Folder layout:\n"
                "`[\"Folder Name\"{\n    Contents\n}]`\n\n"
                "📄 File layout:\n"
                "`Button Name Link`\n"
                "`Button Name startLink endLink`\n\n"
                "Try again or send `/cancel`."
            )
            return True

        total_entries = count_nodes(parsed_entries)
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

        async def create_nodes_recursive(nodes, parent_folder_id):
            nonlocal completed
            for node in nodes:
                if user_id in ADMIN_STATES and ADMIN_STATES[user_id].get("cancel_requested"):
                    status_lines.append("🛑 **Creation stopped by admin.**")
                    return False
                
                if node["type"] == "folder":
                    name = node["name"]
                    try:
                        new_folder_id = await database.create_section(name, series_id, parent_id=parent_folder_id, sec_type="folder")
                        status_lines.append(f"📁 {name} Created")
                        
                        completed += 1
                        display_lines = status_lines[-10:]
                        progress_text = f"⏳ **Creating buttons...**\n\n" + "\n".join(display_lines) + f"\n\nProgress: {completed}/{total_entries}"
                        try:
                            await client.edit_message_text(chat_id=message.chat.id, message_id=progress_msg.id, text=progress_text, reply_markup=reply_markup)
                        except Exception:
                            pass
                        await asyncio.sleep(0.2)
                        
                        if "children" in node and node["children"]:
                            success = await create_nodes_recursive(node["children"], new_folder_id)
                            if not success:
                                return False
                    except Exception as e:
                        status_lines.append(f"❌ Folder: {name} (Error: {e})")
                        completed += 1
                        
                elif node["type"] == "file":
                    name = node["name"]
                    ranges = node["ranges"]
                    
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
                            new_sec_id = await database.create_section(name, series_id, parent_id=parent_folder_id, sec_type="files")
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
            return True

        await create_nodes_recursive(parsed_entries, parent_id)

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
            if '#' in text:
                text = text.split('#', 1)[0].strip()
            # Split by '+'
            parts = [p.strip() for p in text.split('+') if p.strip()]
            if not parts:
                await message.reply_text("❌ Input cannot be empty. Try again or send /cancel.")
                return True
                
            for part in parts:
                tokens = [clean_link_token(w) for w in part.split() if w]
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
