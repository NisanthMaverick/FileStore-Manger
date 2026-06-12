from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import database
from .helpers import (
    ADMIN_STATES, get_readable_size, get_back_button, get_main_panel_markup
)
from .ui_files import (
    show_manage_series, show_manage_files
)

async def handle_files_callbacks(client: Client, callback: CallbackQuery, data: str) -> bool:
    user_id = callback.from_user.id

    if data == "main_panel":
        await callback.answer()
        await callback.message.edit_text(
            "🛠 **Master Admin Control Panel** 🛠\n\nSelect a category below to configure and manage the bot:",
            reply_markup=get_main_panel_markup()
        )
        return True

    elif data == "close_panel":
        await callback.answer("Closing panel...")
        await callback.message.delete()
        return True

    elif data == "manage_files":
        await callback.answer()
        await show_manage_files(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "add_file":
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_file", "message_id": callback.message.id, "data": {}}
        await callback.message.edit_text(
            "📥 **Upload/Store File**\n\nPlease **send or forward** the file (video, document, audio, photo) you want to store permanently.\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([get_back_button("manage_files")])
        )
        return True

    elif data.startswith("list_files_"):
        await callback.answer()
        skip = int(data.split("_")[2])
        files, total = await database.list_files(skip=skip, limit=5)
        
        text = f"📂 **Stored Files List** (Total: {total})\n\n"
        buttons = []
        if not files:
            text += "_No files uploaded yet._"
        else:
            for f in files:
                text += f"▪️ `{f['file_name']}`\n  Size: {get_readable_size(f['file_size'])} | Code: `{f['file_code']}`\n\n"
                buttons.append([InlineKeyboardButton(f"🗑 Delete {f['file_name'][:15]}...", callback_data=f"del_file_{f['file_code']}_{skip}")])
        pag_row = []
        if skip > 0:
            pag_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"list_files_{max(0, skip - 5)}"))
        if skip + 5 < total:
            pag_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"list_files_{skip + 5}"))
        if pag_row:
            buttons.append(pag_row)
        buttons.append(get_back_button("manage_files"))
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
        return True

    elif data.startswith("del_file_"):
        parts = data.split("_")
        file_code = parts[2]
        skip = int(parts[3])
        file_info = await database.get_file(file_code)
        if file_info:
            await database.delete_file(file_code)
            await callback.answer("File deleted successfully!", show_alert=True)
        else:
            await callback.answer("File not found.")
        
        files, total = await database.list_files(skip=skip, limit=5)
        text = f"📂 **Stored Files List** (Total: {total})\n\n"
        buttons = []
        if not files:
            text += "_No files uploaded yet._"
        else:
            for f in files:
                text += f"▪️ `{f['file_name']}`\n  Size: {get_readable_size(f['file_size'])} | Code: `{f['file_code']}`\n\n"
                buttons.append([InlineKeyboardButton(f"🗑 Delete {f['file_name'][:15]}...", callback_data=f"del_file_{f['file_code']}_{skip}")])
        pag_row = []
        if skip > 0:
            pag_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"list_files_{max(0, skip - 5)}"))
        if skip + 5 < total:
            pag_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"list_files_{skip + 5}"))
        if pag_row:
            buttons.append(pag_row)
        buttons.append(get_back_button("manage_files"))
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
        return True

    elif data == "manage_series":
        await callback.answer()
        await show_manage_series(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "create_series":
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_series_title", "message_id": callback.message.id, "data": {}}
        await callback.message.edit_text("🎬 **Create New Series**\n\nPlease enter the **Series Title**:\n\n❌ Send `/cancel` to abort.", reply_markup=InlineKeyboardMarkup([get_back_button("manage_files")]))
        return True

    elif data.startswith("del_series_"):
        series_id = int(data.split("_")[2])
        s = await database.get_series(series_id)
        if s:
            await database.delete_series(series_id)
            await callback.answer("Series deleted successfully!", show_alert=True)
        else:
            await callback.answer("Series not found.")
        await show_manage_series(client, callback.message.chat.id, callback.message.id)
        return True

    return False
