import asyncio
from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import database
from clone_helpers import ACTIVE_CLONES
from config import API_ID, API_HASH

# Dynamic starting of Clone Bots
async def start_clone_bot(token: str) -> bool:
    if token in ACTIVE_CLONES:
        return True

    try:
        client = Client(
            name=f"clone_{token.split(':')[0]}",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=token,
            in_memory=True
        )

        # Import dynamically to avoid circular import issues
        from clone_bot import register_clone_handlers
        register_clone_handlers(client)
        
        await client.start()
        ACTIVE_CLONES[token] = client
        return True
    except Exception as e:
        print(f"Failed to start clone bot: {e}")
        return False

# Stop Clone Bot
async def stop_clone_bot(token: str):
    if token in ACTIVE_CLONES:
        client = ACTIVE_CLONES.pop(token)
        try:
            await client.stop()
        except Exception as e:
            print(f"Failed to stop clone bot gracefully: {e}")

async def show_user_tree(client: Client, chat_id: int, message_id: int, series_id: int, section_id: int = None, is_new_message: bool = False):
    series = await database.get_series(series_id)
    if not series:
        text = "❌ Series not found."
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Categories", callback_data="cl_browse_series_0")]])
        if is_new_message:
            await client.send_message(chat_id=chat_id, text=text, reply_markup=markup)
        else:
            await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
        return

    sections = await database.list_sections(series_id, parent_id=section_id)

    custom_msg = None
    per_row = 2

    if section_id:
        current_sec = await database.get_section(section_id)
        if current_sec:
            custom_msg = current_sec.get("custom_msg")
            per_row = current_sec.get("buttons_per_row", 2)
    else:
        custom_msg = series.get("custom_msg")
        per_row = series.get("buttons_per_row", 2)

    if custom_msg:
        text = custom_msg
    else:
        path_str = f"🎬 **{series['title']}**"
        if section_id:
            sec_path = await database.get_section_path(section_id)
            path_str += f" › {sec_path}"
        text = f"{path_str}\n"
        if series['description'] and not section_id:
            text += f"_{series['description']}_\n"
        text += "\n"

    buttons = []

    if sections:
        row = []
        for s in sections:
            if s.get("sec_type") == "files":
                btn = InlineKeyboardButton(f"📥 {s['name']}", callback_data=f"cl_send_sec_{series_id}_{s['id']}")
            else:
                btn = InlineKeyboardButton(f"📁 {s['name']}", callback_data=f"cl_tree_{series_id}_{s['id']}")
            
            row.append(btn)
            if len(row) == per_row:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
    else:
        text += "_Nothing here yet._\n"

    if section_id:
        parent_id = current_sec["parent_id"] if current_sec else None
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"cl_tree_{series_id}_{parent_id or 0}")])
    else:
        buttons.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="cl_browse_series_0")])

    if is_new_message:
        await client.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        try:
            await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            print(f"Error rendering user tree: {e}")
