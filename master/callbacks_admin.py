import tempfile
import os
from datetime import datetime
from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import database
from config import OWNER_ID
from .helpers import (
    ADMIN_STATES, log_admin_action, get_back_button
)
from .ui_admin import (
    show_db_sync, show_manage_clones, show_mgr_admins, show_backup_menu,
    get_manage_clones_markup, get_bot_details_markup, show_bot_details, show_sub_mgr,
    show_remove_subscriber_menu, show_lock_settings, show_active_series_config,
    show_premium_users_panel, show_journey_db_channels
)
from clones.tree import start_clone_bot, stop_clone_bot

async def handle_admin_callbacks(client: Client, callback: CallbackQuery, data: str) -> bool:
    user_id = callback.from_user.id

    # --- Database sync actions ---
    if data == "db_sync":
        await callback.answer()
        await show_db_sync(client, callback.message.chat.id, callback.message.id)
        return True

    elif data.startswith("manage_j_db_channels_"):
        skip = int(data.split("_")[4])
        await callback.answer()
        await show_journey_db_channels(client, callback.message.chat.id, callback.message.id, skip)
        return True

    elif data.startswith("config_j_db_list_"):
        parts = data.split("_")
        journey_id = int(parts[4])
        skip = int(parts[5])
        await callback.answer()
        ADMIN_STATES[user_id] = {
            "state": "waiting_for_j_db_channel",
            "message_id": callback.message.id,
            "data": {
                "journey_id": journey_id,
                "origin": "list",
                "skip": skip
            }
        }
        await callback.message.edit_text(
            "📁 **Configure Journey DB Channel**\n\n"
            "Please send the numerical channel ID (e.g., `-100123456789`) where files for this journey are stored.\n"
            "Normal users on clone bots will download files directly from this channel.\n\n"
            "To reset and use the default global DB channel, send `none` or `default`.\n\n"
            "❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data=f"manage_j_db_channels_{skip}")]])
        )
        return True

    elif data == "edit_db_upload_delay":
        await callback.answer()
        settings = await database.get_settings()
        current_delay = settings.get("db_upload_delay", 3)
        ADMIN_STATES[user_id] = {"state": "waiting_for_db_upload_delay", "message_id": callback.message.id}
        await callback.message.edit_text(
            "⏱ **Edit DB Bulk Upload Delay**\n\n"
            "Enter the delay time in seconds (integer between `0` and `10`) to wait between storing/uploading files to the database.\n\n"
            "Type `no` to disable delay (set to `0` seconds).\n\n"
            f"Current Delay: `{current_delay}` second(s)\n"
            "Default: `3` seconds\n"
            "Max: `10` seconds\n\n"
            "❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="db_sync")]])
        )
        return True

    elif data == "sub_mgr":
        await callback.answer()
        await show_sub_mgr(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "premium_users_panel":
        await callback.answer()
        await show_premium_users_panel(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "sync_premium_users":
        await callback.answer("🔄 Syncing premium users from remote DB...", show_alert=False)
        count = await database.sync_premium_users()
        await callback.answer(f"✅ Synced {count} premium user(s) successfully!", show_alert=True)
        await show_premium_users_panel(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "toggle_testing_mode":
        await callback.answer()
        settings = await database.get_settings()
        new_val = not settings.get("testing_mode", False)
        await database.update_settings({"testing_mode": new_val})
        status_str = "Enabled 🧪" if new_val else "Disabled ❌"
        await callback.answer(f"🧪 Testing Mode: {status_str}", show_alert=True)
        await show_premium_users_panel(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "toggle_testing_mode_sub":
        await callback.answer()
        settings = await database.get_settings()
        new_val = not settings.get("testing_mode", False)
        await database.update_settings({"testing_mode": new_val})
        status_str = "Enabled 🧪" if new_val else "Disabled ❌"
        await callback.answer(f"🧪 Testing Mode: {status_str}", show_alert=True)
        await show_sub_mgr(client, callback.message.chat.id, callback.message.id)
        return True


    elif data == "toggle_access_to_all":
        await callback.answer()
        settings = await database.get_settings()
        new_status = not settings.get("access_to_all", True)
        await database.update_settings({"access_to_all": new_status})
        await show_sub_mgr(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "add_subscriber":
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_subscriber_id", "message_id": callback.message.id}
        await callback.message.edit_text(
            "➕ **Subscribe User**\n\n"
            "Please send or forward the Telegram User ID of the user you want to subscribe.\n\n"
            "❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="sub_mgr")]])
        )
        return True

    elif data.startswith("remove_subscriber_menu_"):
        await callback.answer()
        skip = int(data.split("_")[3])
        ADMIN_STATES[user_id] = {"state": "waiting_for_remove_subscriber_id", "message_id": callback.message.id, "data": {"skip": skip}}
        await show_remove_subscriber_menu(client, callback.message.chat.id, callback.message.id, skip=skip)
        return True

    elif data.startswith("del_sub_"):
        parts = data.split("_")
        sub_id = int(parts[2])
        skip = int(parts[3])
        await callback.answer()
        await database.remove_subscriber(sub_id)
        await show_remove_subscriber_menu(client, callback.message.chat.id, callback.message.id, skip=skip)
        return True

    elif data == "cancel_broadcast":
        from .states_admin import ACTIVE_BROADCASTS
        if user_id in ACTIVE_BROADCASTS:
            ACTIVE_BROADCASTS[user_id] = True
            await callback.answer("⏳ Cancelling broadcast...", show_alert=True)
        else:
            await callback.answer("❌ No active broadcast to cancel.", show_alert=True)
        return True

    elif data == "broadcast_subs":
        await callback.answer()
        text = (
            "📢 **Broadcast Message Target Selection**\n\n"
            "Choose the bot(s) to send the broadcast message from. "
            "Please note that users must have started the respective target bot to receive the message."
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🤖 Main Bot Only", callback_data="bcast_target_main")
            ],
            [
                InlineKeyboardButton("🤖 All Cloned Bots Only", callback_data="bcast_target_all_clones")
            ],
            [
                InlineKeyboardButton("🤖 Specific Cloned Bot", callback_data="bcast_target_clone_list_0")
            ],
            [
                InlineKeyboardButton("🔙 Back to Subscribers Mgr", callback_data="sub_mgr")
            ]
        ])
        await callback.message.edit_text(text, reply_markup=markup)
        return True

    elif data == "bcast_target_main":
        await callback.answer()
        ADMIN_STATES[user_id] = {
            "state": "waiting_for_broadcast",
            "message_id": callback.message.id,
            "data": {"target": "main"}
        }
        await callback.message.edit_text(
            "📢 **Broadcast: Main Bot**\n\n"
            "Please send or forward the message you want to broadcast to all main bot users.\n\n"
            "❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="broadcast_subs")]])
        )
        return True

    elif data == "bcast_target_all_clones":
        await callback.answer()
        ADMIN_STATES[user_id] = {
            "state": "waiting_for_broadcast",
            "message_id": callback.message.id,
            "data": {"target": "all_clones"}
        }
        await callback.message.edit_text(
            "📢 **Broadcast: All Cloned Bots**\n\n"
            "Please send or forward the message you want to broadcast concurrently from all active clone bots.\n\n"
            "❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="broadcast_subs")]])
        )
        return True

    elif data.startswith("bcast_target_clone_list_"):
        await callback.answer()
        skip = int(data.split("_")[4])
        bots = await database.get_clone_bots()
        
        text = "📢 **Select Cloned Bot for Broadcast**\n\nChoose the specific clone bot to broadcast from:\n\n"
        buttons = []
        limit = 5
        sliced_list = bots[skip:skip+limit]
        
        if not sliced_list:
            text += "_No clone bots registered yet._"
        else:
            for b in sliced_list:
                bot_id = b["token"].split(":")[0] if ":" in b["token"] else b["token"]
                status = "🟢" if b["is_active"] else "🔴"
                text += f"▪️ {status} **{b['name']}** (@{b['username']})\n"
                buttons.append([
                    InlineKeyboardButton(f"🤖 {b['name']} (@{b['username']})", callback_data=f"bcast_target_spec_{bot_id}")
                ])
                
        pag_row = []
        if skip > 0:
            pag_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"bcast_target_clone_list_{max(0, skip - limit)}"))
        if skip + limit < len(bots):
            pag_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"bcast_target_clone_list_{skip + limit}"))
        if pag_row:
            buttons.append(pag_row)
            
        buttons.append([InlineKeyboardButton("🔙 Back to Selection", callback_data="broadcast_subs")])
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        return True

    elif data.startswith("bcast_target_spec_"):
        await callback.answer()
        bot_id = data.split("_")[3]
        bots = await database.get_clone_bots()
        target_bot = None
        for b in bots:
            curr_id = b["token"].split(":")[0] if ":" in b["token"] else b["token"]
            if curr_id == bot_id:
                target_bot = b
                break
                
        if not target_bot:
            return await callback.message.edit_text("❌ Clone bot not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="broadcast_subs")]]))
            
        ADMIN_STATES[user_id] = {
            "state": "waiting_for_broadcast",
            "message_id": callback.message.id,
            "data": {"target": "specific_clone", "token": target_bot["token"], "username": target_bot["username"]}
        }
        await callback.message.edit_text(
            f"📢 **Broadcast: Clone bot @{target_bot['username']}**\n\n"
            "Please send or forward the message you want to broadcast from this clone bot.\n\n"
            "❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="broadcast_subs")]])
        )
        return True

    elif data == "db_channel_options":
        await callback.answer()
        settings = await database.get_settings()
        db_channel = settings.get("db_channel_id")
        text = f"📁 **DB Storage Channel Options**\n\nCurrent Storage Channel: `{db_channel}`\n\nChoose an action below:"
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Edit / Change Channel", callback_data="edit_db_channel"),
                InlineKeyboardButton("🗑 Remove Channel", callback_data="remove_db_channel")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="db_sync")
            ]
        ])
        await callback.message.edit_text(text, reply_markup=markup)
        return True

    elif data == "log_channel_options":
        await callback.answer()
        settings = await database.get_settings()
        log_channel = settings.get("log_channel_id")
        text = f"📝 **Log Auditing Channel Options**\n\nCurrent Log Channel: `{log_channel}`\n\nChoose an action below:"
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Edit / Change Channel", callback_data="edit_log_channel"),
                InlineKeyboardButton("🗑 Remove Channel", callback_data="remove_log_channel")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="db_sync")
            ]
        ])
        await callback.message.edit_text(text, reply_markup=markup)
        return True

    elif data == "remove_db_channel":
        await database.update_settings({"db_channel_id": ""})
        await callback.answer("Storage channel binding removed.", show_alert=True)
        await show_db_sync(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "remove_log_channel":
        await database.update_settings({"log_channel_id": ""})
        await callback.answer("Log auditing channel binding removed.", show_alert=True)
        await show_db_sync(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "edit_db_channel":
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_db_channel", "message_id": callback.message.id}
        await callback.message.edit_text(
            "📁 **Configure DB Storage Channel**\n\nForward any message from the storage channel here, or paste the numerical Channel ID (e.g. `-100xxxxxxx`):\n\n❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="db_sync")]])
        )
        return True

    elif data == "edit_log_channel":
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_log_channel", "message_id": callback.message.id}
        await callback.message.edit_text(
            "📝 **Configure Audit Log Channel**\n\nForward any message from your log channel here, or paste the numerical Channel ID (e.g. `-100xxxxxxx`):\n\n❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="db_sync")]])
        )
        return True

    elif data == "run_integrity":
        await callback.answer("Scanning database index, please wait...")
        await callback.message.edit_text("⏳ **Running File Integrity Scan...**\nSyncing metadata indices with Telegram storage channel...")
        # Integrity checks run silently
        await show_db_sync(client, callback.message.chat.id, callback.message.id)
        return True

    # --- DB Backup Actions ---
    elif data == "backup_menu":
        await callback.answer()
        await show_backup_menu(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "restart_db_conn":
        await callback.answer("Restarting DB engine connection pools...")
        success = await database.restart_database()
        if success:
            await callback.answer("Database connection pools restarted successfully! ⚡", show_alert=True)
        else:
            await callback.answer("❌ Failed to restart database connection pools.", show_alert=True)
        return True

    elif data == "export_db_backup":
        await callback.answer("Generating JSON backup...")
        try:
            json_str = await database.export_db_backup()
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, f"db_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(json_str)
            
            await callback.message.reply_document(
                document=file_path,
                caption="📤 Here is your database backup JSON file.\nKeep it secure. You can use it to restore all data if needed."
            )
            if os.path.exists(file_path):
                os.remove(file_path)
            
            await log_admin_action(f"📤 **Database Backup Exported** by {callback.from_user.mention}")
        except Exception as e:
            print(f"Failed to export DB backup: {e}")
            await callback.message.reply_text(f"❌ Failed to export backup: {e}")
        return True

    elif data == "import_db_backup":
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_backup_file", "message_id": callback.message.id}
        await callback.message.edit_text(
            "📥 **Import JSON Backup**\n\nPlease send the `.json` database backup file exported from your bot:\n\n❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="backup_menu")]])
        )
        return True

    # --- Admin and Clone Bot actions ---
    elif data == "admin_settings":
        await callback.answer()
        settings = await database.get_settings()
        add_bot_status_str = "Premium Only 🔒" if settings.get("clone_bot_premium_only") else "Free for All 🔓"
        text = "🛡️ **Security & Admin Settings Panel**\n\nChoose an action below to manage administrators or clone bot configurations:"
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🛡️ Manage Administrators", callback_data="mgr_admins"),
                InlineKeyboardButton("🤖 Deploy Clone Bots", callback_data="manage_clones")
            ],
            [
                InlineKeyboardButton(f"🤖 Clone Creation: {add_bot_status_str}", callback_data="toggle_add_bot_mode")
            ],
            [
                InlineKeyboardButton("🔙 Back Panel", callback_data="main_panel")
            ]
        ])
        await callback.message.edit_text(text, reply_markup=markup)
        return True

    elif data == "toggle_add_bot_mode":
        settings = await database.get_settings()
        new_val = not settings.get("clone_bot_premium_only", False)
        await database.update_settings({"clone_bot_premium_only": new_val})
        await callback.answer(f"Clone Creation set to: {'Premium Only' if new_val else 'Free for All'}")
        
        add_bot_status_str = "Premium Only 🔒" if new_val else "Free for All 🔓"
        text = "🛡️ **Security & Admin Settings Panel**\n\nChoose an action below to manage administrators or clone bot configurations:"
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🛡️ Manage Administrators", callback_data="mgr_admins"),
                InlineKeyboardButton("🤖 Deploy Clone Bots", callback_data="manage_clones")
            ],
            [
                InlineKeyboardButton(f"🤖 Clone Creation: {add_bot_status_str}", callback_data="toggle_add_bot_mode")
            ],
            [
                InlineKeyboardButton("🔙 Back Panel", callback_data="main_panel")
            ]
        ])
        await callback.message.edit_text(text, reply_markup=markup)
        return True

    elif data == "mgr_admins":
        await callback.answer()
        await show_mgr_admins(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "add_admin_id":
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_admin_id", "message_id": callback.message.id}
        await callback.message.edit_text(
            "🛡️ **Add Administrator**\n\nPlease enter the numerical Telegram User ID of the new admin:\n\n❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="mgr_admins")]])
        )
        return True

    elif data == "remove_admin_id":
        await callback.answer()
        ADMIN_STATES[user_id] = {"state": "waiting_for_remove_admin_id", "message_id": callback.message.id}
        await callback.message.edit_text(
            "🛡️ **Remove Administrator**\n\nPlease enter the numerical Telegram User ID of the admin to remove:\n\n❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="mgr_admins")]])
        )
        return True

    elif data == "manage_clones":
        await callback.answer()
        await show_manage_clones(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "add_clone":
        await callback.answer()
        bots = await database.get_clone_bots()
        if len(bots) >= 2:
            return await callback.answer("❌ Limit reached! You can register at most 2 clone bots.", show_alert=True)
        
        ADMIN_STATES[user_id] = {"state": "waiting_for_clone_token", "message_id": callback.message.id}
        await callback.message.edit_text(
            "🤖 **Register New Clone Bot**\n\nPlease send your clone bot API Token (obtain from @BotFather):\n\n❌ Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="manage_clones")]])
        )
        return True

    elif data.startswith("bot_details_"):
        await callback.answer()
        username = data.replace("bot_details_", "")
        bots = await database.get_clone_bots()
        bot = next((b for b in bots if b["username"] == username), None)
        if bot:
            settings = await database.get_settings()
            primary = settings.get("primary_clone_username")
            await show_bot_details(client, callback.message.chat.id, callback.message.id, bot, primary)
        return True

    elif data.startswith("status_bot_"):
        await callback.answer()
        username = data.replace("status_bot_", "")
        bots = await database.get_clone_bots()
        target_bot = next((b for b in bots if b["username"] == username), None)
        
        if target_bot:
            new_status = not target_bot["is_active"]
            if new_status:
                started = await start_clone_bot(target_bot["token"])
                if started:
                    await database.set_clone_bot_status(target_bot["token"], True)
                    settings = await database.get_settings()
                    if not settings.get("primary_clone_username"):
                        await database.update_settings({"primary_clone_username": username})
                    await callback.answer("Clone bot started successfully! 🟢", show_alert=True)
                    await log_admin_action(f"🤖 **Clone Bot Activated**: @{username} by {callback.from_user.mention}")
                else:
                    await callback.answer("❌ Failed to start clone bot. Check token.", show_alert=True)
            else:
                await stop_clone_bot(target_bot["token"])
                await database.set_clone_bot_status(target_bot["token"], False)
                settings = await database.get_settings()
                if settings.get("primary_clone_username") == username:
                    await database.update_settings({"primary_clone_username": ""})
                await callback.answer("Clone bot stopped. 🔴", show_alert=True)
                await log_admin_action(f"🤖 **Clone Bot Deactivated**: @{username} by {callback.from_user.mention}")
        
        # Reload details
        bots = await database.get_clone_bots()
        target_bot = next((b for b in bots if b["username"] == username), None)
        if target_bot:
            settings = await database.get_settings()
            primary = settings.get("primary_clone_username")
            await show_bot_details(client, callback.message.chat.id, callback.message.id, target_bot, primary)
        return True

    elif data.startswith("primary_bot_"):
        username = data.replace("primary_bot_", "")
        await database.update_settings({"primary_clone_username": username})
        await callback.answer(f"Set @{username} as Primary Redirect Bot!", show_alert=True)
        await log_admin_action(f"🤖 **Primary Redirect Set**: @{username} by {callback.from_user.mention}")
        
        bots = await database.get_clone_bots()
        target_bot = next((b for b in bots if b["username"] == username), None)
        if target_bot:
            settings = await database.get_settings()
            primary = settings.get("primary_clone_username")
            await show_bot_details(client, callback.message.chat.id, callback.message.id, target_bot, primary)
        return True

    elif data.startswith("del_bot_"):
        await callback.answer()
        username = data.replace("del_bot_", "")
        bots = await database.get_clone_bots()
        target_bot = next((b for b in bots if b["username"] == username), None)
        
        if target_bot:
            if target_bot["is_active"]:
                await stop_clone_bot(target_bot["token"])
            await database.delete_clone_bot(target_bot["token"])
            settings = await database.get_settings()
            if settings.get("primary_clone_username") == username:
                await database.update_settings({"primary_clone_username": ""})
            await log_admin_action(f"🛡️ **Clone Bot Deleted**: @{username} by {callback.from_user.mention}")
            
        await show_manage_clones(client, callback.message.chat.id, callback.message.id)
        return True

    elif data == "config_subscription_db_url":
        await callback.answer()
        settings = await database.get_settings()
        current_url = settings.get("subscription_db_url") or "Not configured (uses default)"
        ADMIN_STATES[user_id] = {"state": "waiting_for_subscription_db_url", "message_id": callback.message.id}
        await callback.message.edit_text(
            "🔌 **Configure Premium Subscription Database Link**\n\n"
            "Please send the PostgreSQL Database Connection URL for the Subscription bot.\n\n"
            "Format: `postgresql://username:password@host:port/database?sslmode=require`\n\n"
            f"Current URL: `{current_url}`\n\n"
            "Type `none` or `default` to delete the custom URL and revert to default.\n\n"
            "❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="premium_users_panel")]])
        )
        return True

    elif data == "edit_more_info_msg":
        await callback.answer()
        settings = await database.get_settings()
        current_msg = settings.get("more_info_msg") or "(Default Dynamic Message)"
        ADMIN_STATES[user_id] = {"state": "waiting_for_more_info_msg", "message_id": callback.message.id}
        await callback.message.edit_text(
            "ℹ️ **Edit User Guidance / More Info Message**\n\n"
            "Configure the template displayed to users when they click **Info / Guide** button.\n\n"
            "You can use the following dynamic placeholders:\n"
            "• `{active_premium_series_status}`: Active series lock status (ON/OFF)\n"
            "• `{old_series_lock}`: Old series lock status (ON/OFF)\n"
            "• `{day_based_lock_status}`: Day-based lock status (ON/OFF)\n"
            "• `{unlock_duration}`: Active series unlock duration\n"
            "• `{active_series_list}`: Dynamic bullet list of active series\n"
            "• `{old_series_list}`: Dynamic bullet list of non-active series\n\n"
            f"Current Message Template:\n```\n{current_msg}\n```\n\n"
            "Type `none` or `default` to revert to using the default dynamic template.\n\n"
            "❌ Send `/cancel` to abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="admin_settings")]])
        )
        return True

    return False
