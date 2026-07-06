import asyncio
from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import database
from .helpers import (
    ADMIN_STATES, log_admin_action, get_back_button
)
from .ui_files import (
    show_folder_management, show_series_browse, show_manage_series, show_filesec_actions,
    show_series_management_menu, show_series_reorder_menu,
    show_journey_detail, show_manage_series_journey, show_journey_lock_settings,
    show_journey_active_series_config
)
from .ui_config import show_auto_delete_menu

async def handle_series_callbacks(client: Client, callback: CallbackQuery, data: str) -> bool:
    user_id = callback.from_user.id

    if data.startswith("import_files_"):
        parts = data.split("_")
        series_id = int(parts[2])
        section_id = int(parts[3])
        library_skip = int(parts[4]) if len(parts) > 4 else 0
        await callback.answer()
        sec = await database.get_section(section_id)
        parent_id = sec["parent_id"] if sec else None
        ADMIN_STATES[user_id] = {"state": "waiting_for_tree_file_links", "message_id": callback.message.id, "data": {"series_id": series_id, "section_id": section_id, "parent_folder_id": parent_id, "clear_before": True, "library_skip": library_skip}}
        await callback.message.edit_text(
            f"📥 **{sec['name'] if sec else 'Files'}** — Import Files\n\n"
            "Please **forward a message** or send the **Telegram message link(s)** to import files.\n\n"
            "**Format Guidelines:**\n"
            "• **Single Link:** Paste a single link:\n"
            "  `https://t.me/c/12345/100` or `(https://t.me/c/12345/100)`\n"
            "• **Range of Links:** Paste first and last links with a space:\n"
            "  `https://t.me/c/12345/100 https://t.me/c/12345/110` or `(https://t.me/c/12345/100 https://t.me/c/12345/110)`\n"
            "• **Multiple Ranges:** Separate multiple links or ranges with a `+` symbol:\n"
            "  `link1 + (link2 link3) + link4`\n\n"
            "❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]])
        )
        return True

    elif data.startswith("rename_sec_"):
        parts = data.split("_")
        series_id = int(parts[2])
        section_id = int(parts[3])
        library_skip = int(parts[4]) if len(parts) > 4 else 0
        await callback.answer()
        sec = await database.get_section(section_id)
        if not sec:
            return await callback.message.edit_text("Folder not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"browse_sec_{series_id}_0_{library_skip}")]]))
        ADMIN_STATES[user_id] = {"state": "waiting_for_rename_sec", "message_id": callback.message.id, "data": {"series_id": series_id, "section_id": section_id, "library_skip": library_skip}}
        await callback.message.edit_text(
            f"✏️ **Rename Folder: {sec['name']}**\n\nPlease enter the **New Folder Name / Heading**:\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"browse_sec_{series_id}_{section_id}_{library_skip}")]])
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

    elif data.startswith("move_folder_select_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        skip = int(parts[5])
        await callback.answer()
        from .ui_files import show_move_folder_menu
        await show_move_folder_menu(client, callback.message.chat.id, callback.message.id, series_id, section_id, skip)
        return True

    elif data.startswith("move_folder_execute_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        target_val = parts[5]
        
        target_id = None if target_val == "root" else int(target_val)
        
        await callback.answer("📂 Moving folder...")
        success = await database.update_section_parent(section_id, target_id)
        if success:
            await callback.answer("✅ Folder moved successfully!", show_alert=True)
        else:
            await callback.answer("❌ Failed to move folder.", show_alert=True)
            
        await show_folder_management(client, callback.message.chat.id, callback.message.id, series_id, section_id)
        return True

    elif data.startswith("edit_sec_msg_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        library_skip = int(parts[5]) if len(parts) > 5 else 0
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_folder_msg", "message_id": callback.message.id, "data": {"series_id": series_id, "section_id": section_id, "library_skip": library_skip}}
        await callback.message.edit_text(
            "💬 **Edit Section Custom Message**\n\nSend the custom display message for this folder/section. Send `none` to reset to default.\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]])
        )
        return True

    elif data.startswith("edit_sec_pic_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        library_skip = int(parts[5]) if len(parts) > 5 else 0
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_folder_pic", "message_id": callback.message.id, "data": {"series_id": series_id, "section_id": section_id, "library_skip": library_skip}}
        await callback.message.edit_text(
            "🖼 **Edit Custom Picture**\n\nUpload a picture/photo to be shown in this folder/section browse view. Send `none` to disable/remove the custom picture.\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]])
        )
        return True

    elif data.startswith("edit_sec_cols_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        library_skip = int(parts[5]) if len(parts) > 5 else 0
        await callback.answer()
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("1 Column", callback_data=f"set_sec_cols_{series_id}_{section_id}_1_{library_skip}"), InlineKeyboardButton("2 Columns", callback_data=f"set_sec_cols_{series_id}_{section_id}_2_{library_skip}")],
            [InlineKeyboardButton("3 Columns", callback_data=f"set_sec_cols_{series_id}_{section_id}_3_{library_skip}"), InlineKeyboardButton("4 Columns", callback_data=f"set_sec_cols_{series_id}_{section_id}_4_{library_skip}")],
            [InlineKeyboardButton("🔙 Cancel", callback_data=f"manage_folder_opt_{series_id}_{section_id}_{library_skip}")]
        ])
        await callback.message.edit_text("🔢 **Set Buttons Per Row**\n\nSelect columns layout per row:", reply_markup=markup)
        return True

    elif data.startswith("set_sec_cols_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        num = int(parts[5])
        library_skip = int(parts[6]) if len(parts) > 6 else 0
        await callback.answer(f"Buttons per row set to {num}")
        if section_id == 0:
            await database.update_series_settings(series_id, buttons_per_row=num)
        else:
            await database.update_section_settings(section_id, buttons_per_row=num)
        await show_folder_management(client, callback.message.chat.id, callback.message.id, series_id, section_id, library_skip=library_skip)
        return True

    elif data.startswith("rename_series_opt_"):
        parts = data.split("_")
        series_id = int(parts[3])
        library_skip = int(parts[4]) if len(parts) > 4 else 0
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_rename_series", "message_id": callback.message.id, "data": {"series_id": series_id, "library_skip": library_skip}}
        await callback.message.edit_text("✏️ **Rename Series**\n\nSend the new title for this series:\n\n❌ Send `/cancel` to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]]))
        return True

    elif data.startswith("tree_del_series_"):
        parts = data.split("_")
        series_id = int(parts[3])
        library_skip = int(parts[4]) if len(parts) > 4 else 0
        await callback.answer()
        series = await database.get_series(series_id)
        if not series:
            return await callback.answer("Series not found.")
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("⚠️ Yes, Delete Series", callback_data=f"confirm_del_series_{series_id}_{library_skip}"), InlineKeyboardButton("❌ Cancel", callback_data=f"manage_folder_opt_{series_id}_0_{library_skip}")]])
        await callback.message.edit_text(f"⚠️ **Confirm Delete Series**\n\nAre you sure you want to delete **{series['title']}**? This action is permanent!", reply_markup=markup)
        return True

    elif data.startswith("confirm_del_series_"):
        parts = data.split("_")
        series_id = int(parts[3])
        library_skip = int(parts[4]) if len(parts) > 4 else 0
        series = await database.get_series(series_id)
        if series:
            title = series["title"]
            await database.delete_series(series_id)
            await log_admin_action(f"🗑 **Series Deleted**: `{title}` (ID: {series_id}) by {callback.from_user.mention}")
            await callback.answer("Series deleted successfully.", show_alert=True)
        else:
            await callback.answer("Series not found.")
        await show_manage_series(client, callback.message.chat.id, callback.message.id, skip=library_skip)
        return True

    elif data.startswith("tree_del_sec_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        library_skip = int(parts[5]) if len(parts) > 5 else 0
        await callback.answer()
        sec = await database.get_section(section_id)
        if not sec:
            return await callback.answer("Folder not found.")
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("⚠️ Yes, Delete Folder", callback_data=f"confirm_del_sec_{series_id}_{section_id}_{library_skip}"), InlineKeyboardButton("❌ Cancel", callback_data=f"manage_folder_opt_{series_id}_{section_id}_{library_skip}")]])
        await callback.message.edit_text(f"⚠️ **Confirm Delete Folder**\n\nAre you sure you want to delete **{sec['name']}**? This action is permanent!", reply_markup=markup)
        return True

    elif data.startswith("confirm_del_sec_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        library_skip = int(parts[5]) if len(parts) > 5 else 0
        sec = await database.get_section(section_id)
        parent_id = None
        if sec:
            parent_id = sec["parent_id"]
            await database.delete_section(section_id)
            await callback.answer("Folder deleted successfully.", show_alert=True)
        else:
            await callback.answer("Folder not found.")
        await show_series_browse(client, callback.message.chat.id, callback.message.id, series_id, parent_id, library_skip=library_skip)
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
        library_skip = int(parts[5]) if len(parts) > 5 else 0
        await callback.answer()
        
        text = (
            "➕ **Add Button**\n\n"
            "Select the button type:\n\n"
            "📁 **Folder**: Opens a subfolder section for nested buttons.\n"
            "📄 **File**: Directly delivers content/files to the user."
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📁 Folder", callback_data=f"tree_add_type_folder_{series_id}_{section_id}_{library_skip}"),
                InlineKeyboardButton("📄 File", callback_data=f"tree_add_type_file_{series_id}_{section_id}_{library_skip}")
            ],
            [
                InlineKeyboardButton("🔙 Cancel", callback_data=f"browse_sec_{series_id}_{section_id}_{library_skip}")
            ]
        ])
        await callback.message.edit_text(text, reply_markup=markup)
        return True

    elif data.startswith("tree_bulk_add_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        library_skip = int(parts[5]) if len(parts) > 5 else 0
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_bulk_add", "message_id": callback.message.id, "data": {"series_id": series_id, "section_id": section_id, "library_skip": library_skip}}
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
        library_skip = int(parts[4]) if len(parts) > 4 else 0
        await callback.answer()
        sec = await database.get_section(section_id)
        if not sec:
            return await callback.answer("❌ Section not found.", show_alert=True)
        _, total_files = await database.list_files(skip=0, limit=1, series_id=series_id, section_id=section_id)
        await show_filesec_actions(client, callback.message.chat.id, callback.message.id, series_id, section_id, sec, total_files, library_skip=library_skip)
        return True

    elif data.startswith("filesec_add_"):
        parts = data.split("_")
        series_id = int(parts[2])
        section_id = int(parts[3])
        library_skip = int(parts[4]) if len(parts) > 4 else 0
        await callback.answer()
        sec = await database.get_section(section_id)
        parent_id = sec["parent_id"] if sec else None
        ADMIN_STATES[user_id] = {"state": "waiting_for_tree_file_links", "message_id": callback.message.id, "data": {"series_id": series_id, "section_id": section_id, "parent_folder_id": parent_id, "clear_before": False, "library_skip": library_skip}}
        await callback.message.edit_text(
            f"➕ **Add More Files to: {sec['name'] if sec else 'Button'}**\n\n"
            "Please **forward a message** or send the **Telegram message link(s)** to append files.\n\n"
            "**Format Guidelines:**\n"
            "• **Single Link:** Paste a single link:\n"
            "  `https://t.me/c/12345/100` or `(https://t.me/c/12345/100)`\n"
            "• **Range of Links:** Paste first and last links with a space:\n"
            "  `https://t.me/c/12345/100 https://t.me/c/12345/110` or `(https://t.me/c/12345/100 https://t.me/c/12345/110)`\n"
            "• **Multiple Ranges:** Separate multiple links or ranges with a `+` symbol:\n"
            "  `link1 + (link2 link3) + link4`\n\n"
            "❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"filesec_act_{series_id}_{section_id}_{library_skip}")]]))
        return True

    elif data.startswith("filesec_replace_"):
        parts = data.split("_")
        series_id = int(parts[2])
        section_id = int(parts[3])
        library_skip = int(parts[4]) if len(parts) > 4 else 0
        await callback.answer()
        sec = await database.get_section(section_id)
        parent_id = sec["parent_id"] if sec else None
        ADMIN_STATES[user_id] = {"state": "waiting_for_tree_file_links", "message_id": callback.message.id, "data": {"series_id": series_id, "section_id": section_id, "parent_folder_id": parent_id, "clear_before": True, "library_skip": library_skip}}
        await callback.message.edit_text(
            f"🔄 **Replace All Files in: {sec['name'] if sec else 'Button'}**\n\n"
            "⚠️ **WARNING:** This will delete existing files in this button!\n\n"
            "Please **forward a message** or send the new **Telegram message link(s)**:\n\n"
            "**Format Guidelines:**\n"
            "• **Single Link:** Paste a single link:\n"
            "  `https://t.me/c/12345/100` or `(https://t.me/c/12345/100)`\n"
            "• **Range of Links:** Paste first and last links with a space:\n"
            "  `https://t.me/c/12345/100 https://t.me/c/12345/110` or `(https://t.me/c/12345/100 https://t.me/c/12345/110)`\n"
            "• **Multiple Ranges:** Separate multiple links or ranges with a `+` symbol:\n"
            "  `link1 + (link2 link3) + link4`\n\n"
            "❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"filesec_act_{series_id}_{section_id}_{library_skip}")]]))
        return True

    elif data.startswith("tree_add_type_folder_"):
        parts = data.split("_")
        series_id = int(parts[4])
        section_id = int(parts[5])
        library_skip = int(parts[6]) if len(parts) > 6 else 0
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_tree_folder_name", "message_id": callback.message.id, "data": {"series_id": series_id, "parent_folder_id": section_id, "library_skip": library_skip}}
        await callback.message.edit_text(
            "📁 **Create Folder**\n\nPlease enter the **Folder Name**:\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="tree_cancel_btn")]])
        )
        return True

    elif data.startswith("tree_add_type_file_"):
        parts = data.split("_")
        series_id = int(parts[4])
        section_id = int(parts[5])
        library_skip = int(parts[6]) if len(parts) > 6 else 0
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_tree_file_btn_name", "message_id": callback.message.id, "data": {"series_id": series_id, "parent_folder_id": section_id, "library_skip": library_skip}}
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
            library_skip = state_data["data"].get("library_skip", 0)
            
            if state_name in ["waiting_for_folder_msg", "waiting_for_rename_series", "waiting_for_folder_pic"]:
                target_sec = section_id if section_id is not None else 0
                await show_folder_management(client, callback.message.chat.id, callback.message.id, series_id, target_sec, library_skip=library_skip)
                return True
            
            if state_data["data"].get("is_new_section"):
                new_sec_id = state_data["data"]["section_id"]
                await database.delete_section(new_sec_id)
                await show_series_browse(client, callback.message.chat.id, callback.message.id, series_id, parent_folder_id if parent_folder_id and parent_folder_id > 0 else None, library_skip=library_skip)
            else:
                sec = await database.get_section(section_id)
                if sec:
                    _, total_files = await database.list_files(skip=0, limit=1, series_id=series_id, section_id=section_id)
                    await show_filesec_actions(client, callback.message.chat.id, callback.message.id, series_id, section_id, sec, total_files, library_skip=library_skip)
                else:
                    await show_series_browse(client, callback.message.chat.id, callback.message.id, series_id, parent_folder_id if parent_folder_id and parent_folder_id > 0 else None, library_skip=library_skip)
        return True

    elif data.startswith("manage_journey_"):
        journey_id = int(data.split("_")[2])
        await callback.answer()
        await show_journey_detail(client, callback.message.chat.id, callback.message.id, journey_id)
        return True

    elif data == "create_journey_opt":
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_journey_name", "message_id": callback.message.id}
        await callback.message.edit_text(
            "🗺️ **Create New Journey / Category**\n\nPlease enter the **Journey Name** (e.g., `Movies`, `Weekly Webseries`):\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="manage_series")]])
        )
        return True

    elif data.startswith("rename_journey_opt_"):
        journey_id = int(data.split("_")[3])
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_rename_journey", "message_id": callback.message.id, "data": {"journey_id": journey_id}}
        await callback.message.edit_text(
            "✏️ **Rename Journey**\n\nPlease enter the new name for this journey:\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"manage_journey_{journey_id}")]])
        )
        return True

    elif data.startswith("delete_journey_opt_"):
        journey_id = int(data.split("_")[3])
        await callback.answer()
        j = await database.get_journey(journey_id)
        if not j:
            return await callback.answer("Journey not found.", show_alert=True)
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚠️ Yes, Delete Journey", callback_data=f"confirm_delete_j_{journey_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"manage_journey_{journey_id}")
            ]
        ])
        await callback.message.edit_text(
            f"⚠️ **Confirm Delete Journey**\n\nAre you sure you want to delete **{j['name']}**?\n"
            "This will delete ALL series, folders, and links associated with this journey! This action is permanent!",
            reply_markup=markup
        )
        return True

    elif data.startswith("confirm_delete_j_"):
        journey_id = int(data.split("_")[3])
        j = await database.get_journey(journey_id)
        if j:
            name = j["name"]
            await database.delete_journey(journey_id)
            await log_admin_action(f"🗑 **Journey Deleted**: `{name}` (ID: {journey_id}) by {callback.from_user.mention}")
            await callback.answer("Journey deleted successfully.", show_alert=True)
        else:
            await callback.answer("Journey not found.")
        await show_manage_series(client, callback.message.chat.id, callback.message.id)
        return True

    elif data.startswith("list_j_series_"):
        parts = data.split("_")
        journey_id = int(parts[3])
        skip = int(parts[4])
        await callback.answer()
        await show_manage_series_journey(client, callback.message.chat.id, callback.message.id, journey_id, skip)
        return True

    elif data.startswith("create_series_j_"):
        journey_id = int(data.split("_")[3])
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_series_title_j", "message_id": callback.message.id, "data": {"journey_id": journey_id}}
        await callback.message.edit_text(
            "🎬 **Create New Series**\n\nPlease enter the **Series Title**:\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"list_j_series_{journey_id}_0")]])
        )
    elif data.startswith("config_j_db_"):
        journey_id = int(data.split("_")[3])
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_j_db_channel", "message_id": callback.message.id, "data": {"journey_id": journey_id}}
        await callback.message.edit_text(
            "📁 **Configure Journey DB Channel**\n\n"
            "Please send the numerical channel ID (e.g., `-100123456789`) where files for this journey are stored.\n"
            "Normal users on clone bots will download files directly from this channel.\n\n"
            "To reset and use the default global DB channel, send `none` or `default`.\n\n"
            "❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data=f"manage_journey_{journey_id}")]])
        )
        return True

    elif data.startswith("j_lock_settings_"):
        journey_id = int(data.split("_")[3])
        await callback.answer()
        await show_journey_lock_settings(client, callback.message.chat.id, callback.message.id, journey_id)
        return True

    elif data.startswith("tog_j_is_locked_"):
        journey_id = int(data.split("_")[4])
        j = await database.get_journey(journey_id)
        if j:
            new_val = not j.get("is_locked", False)
            await database.update_journey_settings(journey_id, is_locked=new_val)
            await callback.answer(f"Entire Journey Lock toggled to: {'ON' if new_val else 'OFF'}")
        await show_journey_lock_settings(client, callback.message.chat.id, callback.message.id, journey_id)
        return True

    elif data.startswith("tog_j_lock_b_"):
        journey_id = int(data.split("_")[4])
        j = await database.get_journey(journey_id)
        if j:
            new_val = not j["lock_buttons_enabled"]
            await database.update_journey_settings(journey_id, lock_buttons_enabled=new_val)
            await callback.answer(f"Master Switch toggled to: {'ON' if new_val else 'OFF'}")
        await show_journey_lock_settings(client, callback.message.chat.id, callback.message.id, journey_id)
        return True

    elif data.startswith("tog_j_lock_o_"):
        journey_id = int(data.split("_")[4])
        j = await database.get_journey(journey_id)
        if j:
            new_val = not j["lock_old_series_enabled"]
            await database.update_journey_settings(journey_id, lock_old_series_enabled=new_val)
            await callback.answer(f"Lock Old Series toggled to: {'ON' if new_val else 'OFF'}")
        await show_journey_lock_settings(client, callback.message.chat.id, callback.message.id, journey_id)
        return True

    elif data.startswith("tog_j_lock_a_"):
        journey_id = int(data.split("_")[4])
        j = await database.get_journey(journey_id)
        if j:
            new_val = not j["lock_active_series_enabled"]
            await database.update_journey_settings(journey_id, lock_active_series_enabled=new_val)
            await callback.answer(f"Lock Active Series toggled to: {'ON' if new_val else 'OFF'}")
        await show_journey_lock_settings(client, callback.message.chat.id, callback.message.id, journey_id)
        return True

    elif data.startswith("tog_j_lock_d_"):
        journey_id = int(data.split("_")[4])
        j = await database.get_journey(journey_id)
        if j:
            if not j["lock_active_series_enabled"]:
                await callback.answer("⚠️ Please enable 'Lock Active Series' first!", show_alert=True)
                return True
            new_val = not j["lock_day_based_enabled"]
            await database.update_journey_settings(journey_id, lock_day_based_enabled=new_val)
            await callback.answer(f"Day-Based Lock toggled to: {'ON' if new_val else 'OFF'}")
        await show_journey_lock_settings(client, callback.message.chat.id, callback.message.id, journey_id)
        return True

    elif data.startswith("tog_j_lock_i_"):
        journey_id = int(data.split("_")[4])
        j = await database.get_journey(journey_id)
        if j:
            new_val = not j["lock_individual_enabled"]
            await database.update_journey_settings(journey_id, lock_individual_enabled=new_val)
            await callback.answer(f"Individual Lock Switch toggled to: {'ON' if new_val else 'OFF'}")
        await show_journey_lock_settings(client, callback.message.chat.id, callback.message.id, journey_id)
        return True

    elif data.startswith("reset_j_locks_btn_"):
        journey_id = int(data.split("_")[4])
        await callback.answer()
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Yes, Reset All Locks", callback_data=f"confirm_reset_locks_{journey_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"j_lock_settings_{journey_id}")
            ]
        ])
        await callback.message.edit_text(
            "⚠️ **Confirm Reset All Individual Locks**\n\n"
            "This will remove the individual lock status from ALL series and sections in this journey. "
            "They will all be unlocked by default.",
            reply_markup=markup
        )
        return True

    elif data.startswith("confirm_reset_locks_"):
        journey_id = int(data.split("_")[3])
        await database.reset_journey_locks(journey_id)
        await callback.answer("✅ All individual locks reset successfully!", show_alert=True)
        await show_journey_lock_settings(client, callback.message.chat.id, callback.message.id, journey_id)
        return True

    elif data.startswith("edit_j_unlock_dur_"):
        journey_id = int(data.split("_")[4])
        j = await database.get_journey(journey_id)
        if j and not j["lock_active_series_enabled"]:
            await callback.answer("⚠️ Please enable 'Lock Active Series' first!", show_alert=True)
            return True
        await callback.answer()
        current_window = j["lock_time_window"] if j else 0
        ADMIN_STATES[user_id] = {"state": "waiting_for_j_unlock_duration", "message_id": callback.message.id, "data": {"journey_id": journey_id}}
        await callback.message.edit_text(
            "⏱ **Edit Unlock Duration**\n\n"
            "Specify the period during which new content remains unlocked for non-premium users.\n"
            "Format: number followed by `h` (hours) or `d` (days).\n"
            "Examples: `12h` (12 hours), `1d` (24 hours), `3d` (72 hours).\n\n"
            f"Current Unlock Duration: `{current_window} hour(s)`\n"
            "Type `0`, `no`, or `disable` to only keep the latest item unlocked.\n\n"
            "❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data=f"j_lock_settings_{journey_id}")]])
        )
        return True

    elif data.startswith("config_j_active_"):
        parts = data.split("_")
        journey_id = int(parts[3])
        skip = int(parts[4])
        await callback.answer()
        await show_journey_active_series_config(client, callback.message.chat.id, callback.message.id, journey_id, skip)
        return True

    elif data.startswith("tog_j_ser_active_"):
        parts = data.split("_")
        journey_id = int(parts[4])
        series_id = int(parts[5])
        skip = int(parts[6])
        
        series = await database.get_series(series_id)
        if series:
            new_status = not series.get("is_active", True)
            await database.update_series_settings(series_id, is_active=new_status)
            await callback.answer(f"Toggled {series['title']} active status to: {'Active' if new_status else 'Inactive'}")
        else:
            await callback.answer("Series not found.", show_alert=True)
            
        await show_journey_active_series_config(client, callback.message.chat.id, callback.message.id, journey_id, skip)
        return True

    elif data.startswith("toggle_indiv_lock_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])
        library_skip = int(parts[5]) if len(parts) > 5 else 0
        await callback.answer()
        if section_id == 0:
            s = await database.get_series(series_id)
            if s:
                new_lock = not s.get("is_locked", False)
                await database.update_series_settings(series_id, is_locked=new_lock)
                await callback.answer(f"Individual Lock: {'ON' if new_lock else 'OFF'}")
        else:
            sec = await database.get_section(section_id)
            if sec:
                new_lock = not sec.get("is_locked", False)
                await database.update_section_settings(section_id, is_locked=new_lock)
                await callback.answer(f"Individual Lock: {'ON' if new_lock else 'OFF'}")
        await show_folder_management(client, callback.message.chat.id, callback.message.id, series_id, section_id, library_skip=library_skip)
        return True

    elif data.startswith("j_series_management_menu_"):
        journey_id = int(data.split("_")[4])
        await callback.answer()
        ADMIN_STATES.pop(user_id, None)
        await show_series_management_menu(client, callback.message.chat.id, callback.message.id, journey_id)
        return True

    elif data.startswith("series_reorder_menu_"):
        journey_id = int(data.split("_")[3])
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_reorder", "message_id": callback.message.id, "data": {"selected_ids": [], "journey_id": journey_id}}
        await show_series_reorder_menu(client, callback.message.chat.id, callback.message.id, journey_id, selected_ids=[])
        return True

    elif data.startswith("reorder_toggle_"):
        parts = data.split("_")
        journey_id = int(parts[2])
        series_id = int(parts[3])
        await callback.answer()
        if user_id not in ADMIN_STATES or ADMIN_STATES[user_id].get("state") != "waiting_for_reorder":
            ADMIN_STATES[user_id] = {"state": "waiting_for_reorder", "message_id": callback.message.id, "data": {"selected_ids": [], "journey_id": journey_id}}
        
        selected_ids = ADMIN_STATES[user_id]["data"]["selected_ids"]
        if series_id in selected_ids:
            selected_ids.remove(series_id)
        else:
            selected_ids.append(series_id)
            
        await show_series_reorder_menu(client, callback.message.chat.id, callback.message.id, journey_id, selected_ids=selected_ids)
        return True

    elif data.startswith("reorder_confirm_"):
        journey_id = int(data.split("_")[2])
        if user_id not in ADMIN_STATES or ADMIN_STATES[user_id].get("state") != "waiting_for_reorder":
            await callback.answer("❌ Error: Reordering session expired. Please start over.", show_alert=True)
            await show_series_management_menu(client, callback.message.chat.id, callback.message.id, journey_id)
            return True
            
        selected_ids = ADMIN_STATES[user_id]["data"]["selected_ids"]
        if len(selected_ids) < 2:
            await callback.answer("Please select at least 2 series to reorder.", show_alert=True)
            return True
            
        series_list = await database.list_series(journey_id=journey_id)
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
        await show_series_management_menu(client, callback.message.chat.id, callback.message.id, journey_id)
        return True

    elif data.startswith("edit_series_pag_limit_"):
        journey_id = int(data.split("_")[4])
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_series_pag_limit", "message_id": callback.message.id, "data": {"journey_id": journey_id}}
        await callback.message.edit_text(
            "🔢 **Edit Series Buttons per Page**\n\nEnter the number of series buttons to display on a single page for users (e.g., `5`):\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data=f"j_series_management_menu_{journey_id}")]])
        )
        return True

    elif data.startswith("manage_series_skip_"):
        skip = int(data.split("_")[3])
        await callback.answer()
        await show_manage_series(client, callback.message.chat.id, callback.message.id, skip=skip)
        return True

    elif data.startswith("edit_series_library_msg_"):
        journey_id = int(data.split("_")[4])
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_series_library_msg", "message_id": callback.message.id, "data": {"journey_id": journey_id}}
        await callback.message.edit_text(
            "💬 **Edit Series Library Custom Message**\n\nEnter the custom display message to show above the series categories page. Send `none` to reset:\n\n❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data=f"j_series_management_menu_{journey_id}")]])
        )
        return True

    elif data == "noop":
        await callback.answer()
        return True

    return False
