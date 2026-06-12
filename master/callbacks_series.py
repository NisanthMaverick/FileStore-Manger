import asyncio
from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import database
from .helpers import (
    ADMIN_STATES, log_admin_action, get_back_button
)
from .ui_files import (
    show_folder_management, show_series_browse, show_manage_series, show_filesec_actions
)
from .ui_config import show_auto_delete_menu

async def handle_series_callbacks(client: Client, callback: CallbackQuery, data: str) -> bool:
    user_id = callback.from_user.id

    if data.startswith("import_files_"):
        parts = data.split("_")
        series_id = int(parts[2])
        section_id = int(parts[3])
        await callback.answer()
        sec = await database.get_section(section_id)
        parent_id = sec["parent_id"] if sec else None
        ADMIN_STATES[user_id] = {"state": "waiting_for_start_marker", "message_id": callback.message.id, "data": {"series_id": series_id, "section_id": section_id, "parent_folder_id": parent_id}}
        await callback.message.edit_text(
            "📤 **Add Files - Step 1: Start Marker**\n\nPlease **forward the start message** from the source channel, or **paste the Telegram message link**:\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]])
        )
        return True

    elif data.startswith("rename_sec_"):
        parts = data.split("_")
        series_id = int(parts[2])
        section_id = int(parts[3])
        await callback.answer()
        sec = await database.get_section(section_id)
        if not sec:
            return await callback.message.edit_text("Folder not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"browse_sec_{series_id}_0")]]))
        ADMIN_STATES[user_id] = {"state": "waiting_for_rename_sec", "message_id": callback.message.id, "data": {"series_id": series_id, "section_id": section_id}}
        await callback.message.edit_text(
            f"✏️ **Rename Folder: {sec['name']}**\n\nPlease enter the **New Folder Name / Heading**:\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"browse_sec_{series_id}_{section_id}")]])
        )
        return True

    elif data.startswith("browse_sec_"):
        parts = data.split("_")
        series_id = int(parts[2])
        section_id = int(parts[3])
        await callback.answer()
        await show_series_browse(client, callback.message.chat.id, callback.message.id, series_id, section_id if section_id > 0 else None)
        return True

    elif data.startswith("manage_folder_opt_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        await callback.answer()
        await show_folder_management(client, callback.message.chat.id, callback.message.id, series_id, section_id)
        return True

    elif data.startswith("edit_sec_msg_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_folder_msg", "message_id": callback.message.id, "data": {"series_id": series_id, "section_id": section_id}}
        await callback.message.edit_text(
            "💬 **Edit Section Custom Message**\n\nSend the custom display message for this folder/section. Send `none` to reset to default.\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]])
        )
        return True

    elif data.startswith("edit_sec_cols_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        await callback.answer()
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("1 Column", callback_data=f"set_sec_cols_{series_id}_{section_id}_1"), InlineKeyboardButton("2 Columns", callback_data=f"set_sec_cols_{series_id}_{section_id}_2")],
            [InlineKeyboardButton("3 Columns", callback_data=f"set_sec_cols_{series_id}_{section_id}_3"), InlineKeyboardButton("4 Columns", callback_data=f"set_sec_cols_{series_id}_{section_id}_4")],
            [InlineKeyboardButton("🔙 Cancel", callback_data=f"manage_folder_opt_{series_id}_{section_id}")]
        ])
        await callback.message.edit_text("🔢 **Set Buttons Per Row**\n\nSelect columns layout per row:", reply_markup=markup)
        return True

    elif data.startswith("set_sec_cols_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        num = int(parts[5])
        await callback.answer(f"Buttons per row set to {num}")
        if section_id == 0:
            await database.update_series_settings(series_id, buttons_per_row=num)
        else:
            await database.update_section_settings(section_id, buttons_per_row=num)
        await show_folder_management(client, callback.message.chat.id, callback.message.id, series_id, section_id)
        return True

    elif data.startswith("rename_series_opt_"):
        parts = data.split("_")
        series_id = int(parts[3])
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_rename_series", "message_id": callback.message.id, "data": {"series_id": series_id}}
        await callback.message.edit_text("✏️ **Rename Series**\n\nSend the new title for this series:\n\n❌ Send `/cancel` to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]]))
        return True

    elif data.startswith("tree_del_series_"):
        parts = data.split("_")
        series_id = int(parts[3])
        await callback.answer()
        series = await database.get_series(series_id)
        if not series:
            return await callback.answer("Series not found.")
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("⚠️ Yes, Delete Series", callback_data=f"confirm_del_series_{series_id}"), InlineKeyboardButton("❌ Cancel", callback_data=f"manage_folder_opt_{series_id}_0")]])
        await callback.message.edit_text(f"⚠️ **Confirm Delete Series**\n\nAre you sure you want to delete **{series['title']}**? This action is permanent!", reply_markup=markup)
        return True

    elif data.startswith("confirm_del_series_"):
        parts = data.split("_")
        series_id = int(parts[3])
        series = await database.get_series(series_id)
        if series:
            title = series["title"]
            await database.delete_series(series_id)
            await log_admin_action(f"🗑 **Series Deleted**: `{title}` (ID: {series_id}) by {callback.from_user.mention}")
            await callback.answer("Series deleted successfully.", show_alert=True)
        else:
            await callback.answer("Series not found.")
        await show_manage_series(client, callback.message.chat.id, callback.message.id)
        return True

    elif data.startswith("tree_del_sec_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        await callback.answer()
        sec = await database.get_section(section_id)
        if not sec:
            return await callback.answer("Folder not found.")
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("⚠️ Yes, Delete Folder", callback_data=f"confirm_del_sec_{series_id}_{section_id}"), InlineKeyboardButton("❌ Cancel", callback_data=f"manage_folder_opt_{series_id}_{section_id}")]])
        await callback.message.edit_text(f"⚠️ **Confirm Delete Folder**\n\nAre you sure you want to delete **{sec['name']}**? This action is permanent!", reply_markup=markup)
        return True

    elif data.startswith("confirm_del_sec_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        sec = await database.get_section(section_id)
        parent_id = None
        if sec:
            parent_id = sec["parent_id"]
            await database.delete_section(section_id)
            await callback.answer("Folder deleted successfully.", show_alert=True)
        else:
            await callback.answer("Folder not found.")
        await show_series_browse(client, callback.message.chat.id, callback.message.id, series_id, parent_id)
        return True

    elif data.startswith("del_tree_file_"):
        parts = data.split("_")
        file_code = parts[3]
        series_id = int(parts[4])
        section_id = int(parts[5])
        file_info = await database.get_file(file_code)
        if file_info:
            await database.delete_file(file_code)
            await callback.answer("File deleted successfully!", show_alert=True)
        else:
            await callback.answer("File not found.")
        await show_series_browse(client, callback.message.chat.id, callback.message.id, series_id, section_id if section_id > 0 else None)
        return True

    elif data.startswith("tree_add_btn_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_tree_btn_name", "message_id": callback.message.id, "data": {"series_id": series_id, "parent_folder_id": section_id}}
        await callback.message.edit_text("➕ **Add Button**\n\nPlease enter the **Button Name**:\n\n❌ Send `/cancel` to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]]))
        return True

    elif data.startswith("tree_bulk_add_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_bulk_add", "message_id": callback.message.id, "data": {"series_id": series_id, "section_id": section_id}}
        await callback.message.edit_text(
            "📦 **Bulk Add Files & Folders**\n\nPaste your entries:\n"
            "📁 Folders: `\"Season 1\",`\n"
            "📥 Files: `EP(01) Link1 Link2,`\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]])
        )
        return True

    elif data.startswith("filesec_act_"):
        parts = data.split("_")
        series_id = int(parts[2])
        section_id = int(parts[3])
        await callback.answer()
        sec = await database.get_section(section_id)
        if not sec:
            return await callback.answer("❌ Section not found.", show_alert=True)
        _, total_files = await database.list_files(skip=0, limit=1, series_id=series_id, section_id=section_id)
        await show_filesec_actions(client, callback.message.chat.id, callback.message.id, series_id, section_id, sec, total_files)
        return True

    elif data.startswith("filesec_add_"):
        parts = data.split("_")
        series_id = int(parts[2])
        section_id = int(parts[3])
        await callback.answer()
        sec = await database.get_section(section_id)
        parent_id = sec["parent_id"] if sec else None
        ADMIN_STATES[user_id] = {"state": "waiting_for_start_marker", "message_id": callback.message.id, "data": {"series_id": series_id, "section_id": section_id, "parent_folder_id": parent_id, "clear_before": False}}
        await callback.message.edit_text("➕ **Add More Files — Step 1: Start Marker**\n\nForward start message or paste link:\n\n❌ Send `/cancel` to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"filesec_act_{series_id}_{section_id}")]]))
        return True

    elif data.startswith("filesec_replace_"):
        parts = data.split("_")
        series_id = int(parts[2])
        section_id = int(parts[3])
        await callback.answer()
        sec = await database.get_section(section_id)
        parent_id = sec["parent_id"] if sec else None
        ADMIN_STATES[user_id] = {"state": "waiting_for_start_marker", "message_id": callback.message.id, "data": {"series_id": series_id, "section_id": section_id, "parent_folder_id": parent_id, "clear_before": True}}
        await callback.message.edit_text("🔄 **Replace All Files — Step 1: Start Marker**\n\n⚠️ Will delete existing files in this button.\nForward start message or paste link:\n\n❌ Send `/cancel` to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"filesec_act_{series_id}_{section_id}")]]))
        return True

    elif data == "tree_type_sec":
        await callback.answer()
        state_data = ADMIN_STATES.get(user_id)
        if not state_data or state_data["state"] != "waiting_for_tree_btn_type":
            return True
        series_id = state_data["data"]["series_id"]
        parent_folder_id = state_data["data"]["parent_folder_id"]
        button_name = state_data["data"]["button_name"]
        parent_id = parent_folder_id if parent_folder_id > 0 else None
        await database.create_section(button_name, series_id, parent_id=parent_id, sec_type="folder")
        ADMIN_STATES.pop(user_id, None)
        await show_series_browse(client, callback.message.chat.id, callback.message.id, series_id, parent_folder_id if parent_folder_id > 0 else None)
        return True

    elif data == "tree_type_files":
        await callback.answer()
        state_data = ADMIN_STATES.get(user_id)
        if not state_data or state_data["state"] != "waiting_for_tree_btn_type":
            return True
        ADMIN_STATES[user_id]["state"] = "waiting_for_tree_file_name"
        button_name = state_data["data"]["button_name"]
        await callback.message.edit_text(
            f"📄 **Add File Button: {button_name}**\n\nPlease enter the **File Name**:\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]])
        )
        return True

    elif data == "tree_cancel_btn":
        await callback.answer()
        state_data = ADMIN_STATES.pop(user_id, None)
        if state_data:
            state_name = state_data.get("state")
            if state_name == "waiting_for_auto_delete_duration":
                await show_auto_delete_menu(client, callback.message.chat.id, callback.message.id)
                return True
            
            series_id = state_data["data"].get("series_id")
            parent_folder_id = state_data["data"].get("parent_folder_id")
            section_id = state_data["data"].get("section_id")
            
            if state_name in ["waiting_for_folder_msg", "waiting_for_rename_series"]:
                target_sec = section_id if section_id is not None else 0
                await show_folder_management(client, callback.message.chat.id, callback.message.id, series_id, target_sec)
                return True
            
            if state_data["data"].get("is_new_section"):
                new_sec_id = state_data["data"]["section_id"]
                await database.delete_section(new_sec_id)
                await show_series_browse(client, callback.message.chat.id, callback.message.id, series_id, parent_folder_id if parent_folder_id and parent_folder_id > 0 else None)
            else:
                sec = await database.get_section(section_id)
                if sec:
                    _, total_files = await database.list_files(skip=0, limit=1, series_id=series_id, section_id=section_id)
                    await show_filesec_actions(client, callback.message.chat.id, callback.message.id, series_id, section_id, sec, total_files)
                else:
                    await show_series_browse(client, callback.message.chat.id, callback.message.id, series_id, parent_folder_id if parent_folder_id and parent_folder_id > 0 else None)
        return True

    return False
