import asyncio
from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import database
from .helpers import (
    ADMIN_STATES, log_admin_action, get_back_button
)
from .ui_files import (
    show_folder_management, show_series_browse, show_manage_series, show_filesec_actions,
    show_series_management_menu, show_series_reorder_menu
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
        
        text = (
            "➕ **Add Button**\n\n"
            "Select the button type:\n\n"
            "📁 **Folder**: Opens a subfolder section for nested buttons.\n"
            "📄 **File**: Directly delivers content/files to the user."
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📁 Folder", callback_data=f"tree_add_type_folder_{series_id}_{section_id}"),
                InlineKeyboardButton("📄 File", callback_data=f"tree_add_type_file_{series_id}_{section_id}")
            ],
            [
                InlineKeyboardButton("🔙 Cancel", callback_data=f"browse_sec_{series_id}_{section_id}")
            ]
        ])
        await callback.message.edit_text(text, reply_markup=markup)
        return True

    elif data.startswith("tree_bulk_add_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_bulk_add", "message_id": callback.message.id, "data": {"series_id": series_id, "section_id": section_id}}
        await callback.message.edit_text(
            "📦 **Bulk Add Files & Folders**\n\n"
            "Paste your entries (separated by newlines or commas):\n\n"
            "📁 Folder: `\"Folder Name\"`\n"
            "📥 File/Button: `Button Name startLink endLink`\n\n"
            "💡 **Example:**\n"
            "`\"Season 1\", Episode 01 startLink endLink, Episode 02 startLink endLink`\n\n"
            "❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]])
        )
        return True

    elif data.startswith("stop_bulk_add_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        await callback.answer("🛑 Stopping bulk creation...", show_alert=True)
        if user_id in ADMIN_STATES and ADMIN_STATES[user_id].get("state") == "bulk_adding":
            ADMIN_STATES[user_id]["cancel_requested"] = True
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

    elif data.startswith("tree_add_type_folder_"):
        parts = data.split("_")
        series_id = int(parts[4])
        section_id = int(parts[5])
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_tree_folder_name", "message_id": callback.message.id, "data": {"series_id": series_id, "parent_folder_id": section_id}}
        await callback.message.edit_text(
            "📁 **Create Folder**\n\nPlease enter the **Folder Name**:\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]])
        )
        return True

    elif data.startswith("tree_add_type_file_"):
        parts = data.split("_")
        series_id = int(parts[4])
        section_id = int(parts[5])
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_tree_file_btn_name", "message_id": callback.message.id, "data": {"series_id": series_id, "parent_folder_id": section_id}}
        await callback.message.edit_text(
            "📄 **Add File Button**\n\nPlease enter the **Button / File Name**:\n\n❌ Send `/cancel` to abort.",
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

    elif data == "series_management_menu":
        await callback.answer()
        ADMIN_STATES.pop(user_id, None)
        await show_series_management_menu(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "series_reorder_menu":
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_reorder", "message_id": callback.message.id, "data": {"selected_ids": []}}
        await show_series_reorder_menu(client, callback.message.chat.id, callback.message.id, selected_ids=[])
        return True

    elif data.startswith("reorder_toggle_"):
        series_id = int(data.split("_")[2])
        await callback.answer()
        if user_id not in ADMIN_STATES or ADMIN_STATES[user_id].get("state") != "waiting_for_reorder":
            ADMIN_STATES[user_id] = {"state": "waiting_for_reorder", "message_id": callback.message.id, "data": {"selected_ids": []}}
        
        selected_ids = ADMIN_STATES[user_id]["data"]["selected_ids"]
        if series_id in selected_ids:
            selected_ids.remove(series_id)
        else:
            selected_ids.append(series_id)
            
        await show_series_reorder_menu(client, callback.message.chat.id, callback.message.id, selected_ids=selected_ids)
        return True

    elif data == "reorder_confirm":
        if user_id not in ADMIN_STATES or ADMIN_STATES[user_id].get("state") != "waiting_for_reorder":
            await callback.answer("❌ Error: Reordering session expired. Please start over.", show_alert=True)
            await show_series_management_menu(client, callback.message.chat.id, callback.message.id)
            return True
            
        selected_ids = ADMIN_STATES[user_id]["data"]["selected_ids"]
        if len(selected_ids) < 2:
            await callback.answer("Please select at least 2 series to reorder.", show_alert=True)
            return True
            
        series_list = await database.list_series()
        ordered_ids = []
        ordered_ids.extend(selected_ids)
        for s in series_list:
            sid = s["id"]
            if sid not in selected_ids:
                ordered_ids.append(sid)
                
        for index, sid in enumerate(ordered_ids):
            await database.update_series_settings(sid, display_order=index)
            
        ADMIN_STATES.pop(user_id, None)
        await callback.answer("✅ Series list reordered successfully!", show_alert=True)
        await show_series_management_menu(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "edit_series_pag_limit":
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_series_pag_limit", "message_id": callback.message.id}
        await callback.message.edit_text(
            "🔢 **Edit Series Buttons per Page**\n\nEnter the number of series buttons to display on a single page for users (e.g., `5`):\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="series_management_menu")]])
        )
        return True

    elif data.startswith("manage_series_skip_"):
        skip = int(data.split("_")[3])
        await callback.answer()
        await show_manage_series(client, callback.message.chat.id, callback.message.id, skip=skip)
        return True

    elif data == "edit_series_library_msg":
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_series_library_msg", "message_id": callback.message.id}
        await callback.message.edit_text(
            "💬 **Edit Series Library Custom Message**\n\nEnter the custom display message to show above the series categories page. Send `none` to reset:\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="series_management_menu")]])
        )
        return True

    elif data == "noop":
        await callback.answer()
        return True

    return False
