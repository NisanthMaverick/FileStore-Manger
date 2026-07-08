import asyncio
import os
from datetime import datetime
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait
import database
from config import OWNER_ID
from .helpers import (
    ADMIN_STATES, log_admin_action, get_back_button
)
from .ui_config import show_auto_delete_menu
from .ui_admin import show_db_sync, show_mgr_admins, show_lock_settings

ACTIVE_BROADCASTS = {}

async def handle_admin_states(client: Client, message: Message, state: str, state_data: dict, message_id: int) -> bool:
    user_id = message.from_user.id

    # Delegate FSub and welcome templates states
    from .states_admin_fsub import handle_fsub_states
    if await handle_fsub_states(client, message, state, state_data, message_id):
        return True

    # Delegate custom buttons and clone registration states
    from .states_admin_buttons import handle_buttons_states
    if await handle_buttons_states(client, message, state, state_data, message_id):
        return True

    # 1. Waiting for Broadcast Message
    if state == "waiting_for_broadcast":
        target_info = state_data.get("data", {})
        target_type = target_info.get("target", "main")
        
        ADMIN_STATES.pop(user_id, None)
        if message_id:
            try:
                await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text="📢 **Broadcasting message to all subscribers... Please wait.**")
            except Exception:
                pass

        users = await database.list_users(limit=10000)
        success = 0
        failed = 0
        
        from clones.helpers import ACTIVE_CLONES
        
        # Determine the target client(s) to send the broadcast from
        clients_to_broadcast = []
        if target_type == "main":
            clients_to_broadcast.append(("Main Bot", client))
        elif target_type == "all_clones":
            for token, clone_client in ACTIVE_CLONES.items():
                name = getattr(clone_client.me, "username", None) or getattr(clone_client.me, "first_name", "Clone")
                clients_to_broadcast.append((f"@{name}", clone_client))
        elif target_type == "specific_clone":
            token = target_info.get("token")
            username = target_info.get("username", "Clone")
            clone_client = ACTIVE_CLONES.get(token)
            if not clone_client:
                prefix = token.split(":")[0] if ":" in token else token
                for t, c in ACTIVE_CLONES.items():
                    if t.startswith(prefix):
                        clone_client = c
                        break
            if clone_client:
                clients_to_broadcast.append((f"@{username}", clone_client))
            else:
                report_text = f"❌ **Broadcast Failed**: Clone bot @{username} is not running in memory. Please start it first."
                markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Users", callback_data="sub_mgr")]])
                if message_id:
                    try:
                        await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=report_text, reply_markup=markup)
                    except Exception:
                        await message.reply_text(report_text, reply_markup=markup)
                else:
                    await message.reply_text(report_text, reply_markup=markup)
                return True

        if not clients_to_broadcast:
            report_text = "❌ **Broadcast Failed**: No active bot targets found."
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Users", callback_data="sub_mgr")]])
            if message_id:
                try:
                    await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=report_text, reply_markup=markup)
                except Exception:
                    await message.reply_text(report_text, reply_markup=markup)
            else:
                await message.reply_text(report_text, reply_markup=markup)
            return True

        # Copy the message to the DB Storage Channel if configured, so clone bots can access/copy it.
        settings = await database.get_settings()
        db_channel = settings.get("db_channel_id")
        has_clones = target_type in ["all_clones", "specific_clone"]
        
        if has_clones and not db_channel:
            report_text = "❌ **Broadcast Failed**: DB Storage Channel is not configured. Clone bots require a storage channel to copy/broadcast messages."
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Users", callback_data="sub_mgr")]])
            if message_id:
                try:
                    await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=report_text, reply_markup=markup)
                except Exception:
                    await message.reply_text(report_text, reply_markup=markup)
            else:
                await message.reply_text(report_text, reply_markup=markup)
            return True

        temp_msg_id = None
        source_chat_id = message.chat.id
        source_msg_id = message.id
        
        if db_channel:
            try:
                dest_chat = int(db_channel) if str(db_channel).startswith("-100") or str(db_channel).isdigit() else db_channel
                temp_msg = await client.copy_message(chat_id=dest_chat, from_chat_id=message.chat.id, message_id=message.id)
                temp_msg_id = temp_msg.id
                source_chat_id = dest_chat
                source_msg_id = temp_msg_id
            except Exception as e:
                if has_clones:
                    report_text = f"❌ **Broadcast Failed**: Could not copy message to DB Storage Channel: {e}"
                    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Users", callback_data="sub_mgr")]])
                    if message_id:
                        try:
                            await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=report_text, reply_markup=markup)
                        except Exception:
                            await message.reply_text(report_text, reply_markup=markup)
                    else:
                        await message.reply_text(report_text, reply_markup=markup)
                    return True

        # Perform the broadcast
        import time
        ACTIVE_BROADCASTS[user_id] = False
        last_update_time = time.time()
        
        total_users = len(users)
        total_bots = len(clients_to_broadcast)
        total_expected = total_users * total_bots
        
        overall_sent = 0
        overall_success = 0
        overall_failed = 0
        detail_results = []
        cancelled = False

        for name, bot_client in clients_to_broadcast:
            bot_success = 0
            bot_failed = 0
            for idx, u in enumerate(users, 1):
                if ACTIVE_BROADCASTS.get(user_id, False):
                    cancelled = True
                    break
                
                target_user_id = u["user_id"]
                user_display = f"@{u['username']}" if u.get("username") else f"`{target_user_id}`"
                
                # Periodically update progress message (every 2 seconds)
                now = time.time()
                if now - last_update_time >= 2.0:
                    last_update_time = now
                    remaining = total_expected - overall_sent
                    progress_text = (
                        f"📢 **Broadcasting Message...**\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🤖 **Current Bot:** {name}\n"
                        f"👤 **Sending to:** {user_display}\n"
                        f"📊 **Overall Progress:** {overall_sent}/{total_expected} messages\n"
                        f"⏳ **Total Remaining:** {remaining}\n\n"
                        f"✅ **Total Success:** {overall_success} | ❌ **Total Failed:** {overall_failed}\n"
                        f"• **Current Bot Success:** {bot_success} | ❌ {bot_failed}\n\n"
                        f"⚠️ _Updating live..._"
                    )
                    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Cancel Broadcast", callback_data="cancel_broadcast")]])
                    if message_id:
                        try:
                            await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=progress_text, reply_markup=markup)
                        except Exception:
                            pass
                
                try:
                    await bot_client.copy_message(chat_id=target_user_id, from_chat_id=source_chat_id, message_id=source_msg_id)
                    bot_success += 1
                    overall_success += 1
                except FloodWait as fw:
                    await asyncio.sleep(fw.value)
                    try:
                        await bot_client.copy_message(chat_id=target_user_id, from_chat_id=source_chat_id, message_id=source_msg_id)
                        bot_success += 1
                        overall_success += 1
                    except Exception:
                        bot_failed += 1
                        overall_failed += 1
                except Exception:
                    bot_failed += 1
                    overall_failed += 1
                
                overall_sent += 1
                await asyncio.sleep(0.05)
                
            detail_results.append(f"• **{name}:** ✅ {bot_success} | ❌ {bot_failed}")
            if cancelled:
                break
                
        # Clean up cancel flag
        ACTIVE_BROADCASTS.pop(user_id, None)
        
        # Clean up temporary message in DB channel
        if temp_msg_id and db_channel:
            try:
                dest_chat = int(db_channel) if str(db_channel).startswith("-100") or str(db_channel).isdigit() else db_channel
                await client.delete_messages(chat_id=dest_chat, message_ids=[temp_msg_id])
            except Exception as e:
                print(f"Failed to delete temp broadcast message: {e}")

        if cancelled:
            report_text = (
                f"🛑 **Broadcast Cancelled by Admin**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 **Messages Processed:** {overall_sent}/{total_expected}\n"
                f"✅ **Total Success:** {overall_success}\n"
                f"❌ **Total Failed:** {overall_failed}"
            )
        else:
            detail_str = "\n".join(detail_results)
            report_text = (
                f"📢 **Broadcast Completed**\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{detail_str}\n\n"
                f"📊 **Total Success:** {overall_success}\n"
                f"❌ **Total Failed:** {overall_failed}"
            )
            
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Users", callback_data="sub_mgr")]])
        if message_id:
            try:
                await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=report_text, reply_markup=markup)
            except Exception:
                await message.reply_text(report_text, reply_markup=markup)
        else:
            await message.reply_text(report_text, reply_markup=markup)
        return True

    # 2. Waiting for DB Channel ID
    elif state == "waiting_for_db_channel":
        channel_id = None
        if message.forward_origin:
            origin = message.forward_origin
            if hasattr(origin, "chat") and origin.chat:
                channel_id = str(origin.chat.id)
            elif hasattr(origin, "sender_chat") and origin.sender_chat:
                channel_id = str(origin.sender_chat.id)
        if not channel_id and message.forward_from_chat:
            channel_id = str(message.forward_from_chat.id)
        if not channel_id:
            channel_id = message.text.strip() if message.text else ""
            
        await database.update_settings({"db_channel_id": channel_id})
        ADMIN_STATES.pop(user_id, None)
        if message_id:
            await show_db_sync(client, message.chat.id, message_id)
        else:
            await message.reply_text("✅ Storage channel updated!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="db_sync")]]))
        return True

    # 3. Waiting for Log Channel ID
    elif state == "waiting_for_log_channel":
        channel_id = None
        if message.forward_origin:
            origin = message.forward_origin
            if hasattr(origin, "chat") and origin.chat:
                channel_id = str(origin.chat.id)
            elif hasattr(origin, "sender_chat") and origin.sender_chat:
                channel_id = str(origin.sender_chat.id)
        if not channel_id and message.forward_from_chat:
            channel_id = str(message.forward_from_chat.id)
        if not channel_id:
            channel_id = message.text.strip() if message.text else ""
            
        await database.update_settings({"log_channel_id": channel_id})
        ADMIN_STATES.pop(user_id, None)
        if message_id:
            await show_db_sync(client, message.chat.id, message_id)
        else:
            await message.reply_text("✅ Log channel updated!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="db_sync")]]))
        return True

    # 4. Waiting for new Admin ID
    elif state == "waiting_for_admin_id":
        val = message.text.strip()
        if not val.isdigit():
            return await message.reply_text("⚠️ Please enter a valid numerical User ID, or /cancel.")
        
        admin_id = int(val)
        await database.add_admin(admin_id)
        ADMIN_STATES.pop(user_id, None)
        await log_admin_action(f"🛡️ **Admin Added**: `{admin_id}` by {message.from_user.mention}")
        
        if message_id:
            await show_mgr_admins(client, message.chat.id, message_id)
        else:
            await message.reply_text(f"✅ Added {admin_id} to admins list.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="mgr_admins")]]))
        return True

    # 5. Waiting for Admin ID to remove
    elif state == "waiting_for_remove_admin_id":
        val = message.text.strip()
        if not val.isdigit():
            return await message.reply_text("⚠️ Please enter a valid numerical User ID, or /cancel.")
        
        admin_id = int(val)
        if admin_id == OWNER_ID:
            return await message.reply_text("⚠️ You cannot remove the Master Owner from admins!")
        
        await database.remove_admin(admin_id)
        ADMIN_STATES.pop(user_id, None)
        await log_admin_action(f"🛡️ **Admin Removed**: `{admin_id}` by {message.from_user.mention}")
        
        if message_id:
            await show_mgr_admins(client, message.chat.id, message_id)
        else:
            await message.reply_text(f"✅ Removed {admin_id} from admins list.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="mgr_admins")]]))
        return True

    # 5.5 Waiting for Lock Unlock Duration Window
    elif state == "waiting_for_unlock_duration":
        val = message.text.strip().lower()
        if val in ["0", "no", "disable", "none"]:
            hours = 0
        else:
            import re
            match = re.match(r"^(\d+)\s*(h|d)?$", val)
            if not match:
                return await message.reply_text(
                    "⚠️ Invalid duration format. Please enter a number followed by `h` (hours) or `d` (days).\n"
                    "Examples: `12h`, `2d`, or type `0` to disable duration lock."
                )
            num = int(match.group(1))
            unit = match.group(2) or "h"
            if unit == "d":
                hours = num * 24
            else:
                hours = num
                
        await database.update_settings({"lock_time_window": hours})
        ADMIN_STATES.pop(user_id, None)
        
        if hours == 0:
            feedback_str = "Unlock duration disabled (only the latest content stays unlocked)."
        elif hours % 24 == 0:
            feedback_str = f"Unlock duration set to {hours // 24} day(s)."
        else:
            feedback_str = f"Unlock duration set to {hours} hour(s)."
            
        await log_admin_action(f"🔒 **Lock Duration Updated**: `{feedback_str}` by {message.from_user.mention}")
        
        if message_id:
            try:
                await show_lock_settings(client, message.chat.id, message_id)
            except Exception:
                await message.reply_text(f"✅ {feedback_str}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="lock_settings")]]))
        else:
            await message.reply_text(f"✅ {feedback_str}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="lock_settings")]]))
        return True

    # 6. Waiting for File Auto Delete Duration
    elif state == "waiting_for_auto_delete_duration":
        val = message.text.strip()
        if not val.isdigit() or int(val) <= 0:
            text = "⚠️ **Invalid duration.** Please enter a positive integer (minutes) or send /cancel to abort."
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="auto_delete_menu")]])
            if message_id:
                try:
                    await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=text, reply_markup=markup)
                    return True
                except Exception:
                    pass
            await message.reply_text(text, reply_markup=markup)
            return True
        
        await database.update_settings({"auto_delete_duration": int(val)})
        ADMIN_STATES.pop(user_id, None)
        if message_id:
            await show_auto_delete_menu(client, message.chat.id, message_id)
        else:
            await message.reply_text("✅ Auto delete duration updated successfully!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="auto_delete_menu")]]))
        return True

    # 7. Waiting for JSON Backup File
    elif state == "waiting_for_backup_file":
        doc = message.document
        if not doc or not doc.file_name.endswith(".json"):
            text = "⚠️ **Invalid file.** Please send a valid `.json` backup file or send /cancel to abort."
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="backup_menu")]])
            if message_id:
                try:
                    await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=text, reply_markup=markup)
                    return True
                except Exception:
                    pass
            await message.reply_text(text, reply_markup=markup)
            return True

        if message_id:
            try:
                await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text="⏳ **Importing and restoring backup data... Please wait.**")
            except Exception:
                pass

        file_path = await message.download()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                json_str = f.read()
            success = await database.import_db_backup(json_str)
            ADMIN_STATES.pop(user_id, None)
            if success:
                await log_admin_action(f"📥 **Settings and Database Imported Successfully** by {message.from_user.mention}")
                text = "✅ **Backup imported successfully!** All settings, clone bots, users, and files have been restored."
            else:
                text = "❌ Failed to import backup. Ensure the JSON file is correct."
        except Exception as e:
            ADMIN_STATES.pop(user_id, None)
            text = f"❌ Error importing backup: {e}"
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="db_sync")]])
        if message_id:
            try:
                await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=text, reply_markup=markup)
            except Exception:
                await message.reply_text(text, reply_markup=markup)
        else:
            await message.reply_text(text, reply_markup=markup)
        return True

    elif state == "waiting_for_start_msg":
        ADMIN_STATES.pop(user_id, None)
        settings = await database.get_settings()
        db_channel = settings.get("db_channel_id")
        dest_chat = int(db_channel) if db_channel.startswith("-100") or db_channel.isdigit() else db_channel
        
        try:
            copied = await message.copy(chat_id=dest_chat)
            db_message_id = copied.id
            await database.update_settings({"start_msg_db_id": db_message_id})
            text = "✅ **Start Message configured successfully!**"
        except Exception as e:
            text = f"❌ **Failed to set Start Message:** {e}"

        from .ui_config import show_start_end_msg_menu
        if message_id:
            try:
                await message.reply_text(text)
                await show_start_end_msg_menu(client, message.chat.id, message_id)
            except Exception:
                await message.reply_text(text)
        else:
            await message.reply_text(text)
        return True

    elif state == "waiting_for_end_msg":
        ADMIN_STATES.pop(user_id, None)
        settings = await database.get_settings()
        db_channel = settings.get("db_channel_id")
        dest_chat = int(db_channel) if db_channel.startswith("-100") or db_channel.isdigit() else db_channel
        
        try:
            copied = await message.copy(chat_id=dest_chat)
            db_message_id = copied.id
            await database.update_settings({"end_msg_db_id": db_message_id})
            text = "✅ **End Message configured successfully!**"
        except Exception as e:
            text = f"❌ **Failed to set End Message:** {e}"

        from .ui_config import show_start_end_msg_menu
        if message_id:
            try:
                await message.reply_text(text)
                await show_start_end_msg_menu(client, message.chat.id, message_id)
            except Exception:
                await message.reply_text(text)
        else:
            await message.reply_text(text)
        return True

    elif state == "waiting_for_series_pag_limit":
        ADMIN_STATES.pop(user_id, None)
        limit_text = message.text.strip() if message.text else ""
        try:
            limit = int(limit_text)
            if limit < 1 or limit > 50:
                raise ValueError("Limit must be between 1 and 50")
            await database.update_settings({"series_buttons_per_page": limit})
            text = f"✅ **Series Buttons per Page updated to {limit}!**"
        except Exception as e:
            text = f"❌ **Invalid number:** {e}"

        from .ui_files import show_series_management_menu
        if message_id:
            try:
                await message.reply_text(text)
                await show_series_management_menu(client, message.chat.id, message_id)
            except Exception:
                await message.reply_text(text)
        else:
            await message.reply_text(text)
        return True

    elif state == "waiting_for_series_library_msg":
        ADMIN_STATES.pop(user_id, None)
        msg_text = message.text.strip() if message.text else ""
        
        if msg_text.lower() == "none":
            await database.update_settings({"series_library_custom_msg": None})
            text = "✅ **Series Library Custom Message reset successfully!**"
        else:
            await database.update_settings({"series_library_custom_msg": msg_text})
            text = "✅ **Series Library Custom Message updated successfully!**"

        from .ui_files import show_series_management_menu
        if message_id:
            try:
                await message.reply_text(text)
                await show_series_management_menu(client, message.chat.id, message_id)
            except Exception:
                await message.reply_text(text)
        else:
            await message.reply_text(text)
        return True

    elif state == "waiting_for_user_send_delay":
        val = message.text.strip().lower() if message.text else ""
        
        if val == "no" or val == "no delay":
            delay = 0
        else:
            if not val.isdigit() or int(val) < 0 or int(val) > 10:
                text = "⚠️ **Invalid input.** Please enter an integer between `0` and `10`, or type `no` for no delay. Send `/cancel` to abort."
                markup = InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="bot_config")]])
                if message_id:
                    try:
                        await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=text, reply_markup=markup)
                        return True
                    except Exception:
                        pass
                await message.reply_text(text, reply_markup=markup)
                return True
            delay = int(val)
            
        await database.update_settings({"user_send_delay": delay})
        ADMIN_STATES.pop(user_id, None)
        
        from .ui_config import show_bot_config
        text = f"✅ **User File Send Delay updated to `{delay}` second(s) successfully!**"
        if message_id:
            try:
                await message.reply_text(text)
                await show_bot_config(client, message.chat.id, message_id)
            except Exception:
                await message.reply_text(text)
        else:
            await message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Configurations", callback_data="bot_config")]]))
        return True

    elif state == "waiting_for_db_upload_delay":
        val = message.text.strip().lower() if message.text else ""
        
        if val == "no" or val == "no delay":
            delay = 0
        else:
            if not val.isdigit() or int(val) < 0 or int(val) > 10:
                text = "⚠️ **Invalid input.** Please enter an integer between `0` and `10`, or type `no` for no delay. Send `/cancel` to abort."
                markup = InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="db_sync")]])
                if message_id:
                    try:
                        await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=text, reply_markup=markup)
                        return True
                    except Exception:
                        pass
                await message.reply_text(text, reply_markup=markup)
                return True
            delay = int(val)
            
        await database.update_settings({"db_upload_delay": delay})
        ADMIN_STATES.pop(user_id, None)
        
        from .ui_admin import show_db_sync
        text = f"✅ **DB Bulk Upload Delay updated to `{delay}` second(s) successfully!**"
        if message_id:
            try:
                await message.reply_text(text)
                await show_db_sync(client, message.chat.id, message_id)
            except Exception:
                await message.reply_text(text)
        else:
            await message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Database Engine", callback_data="db_sync")]]))
        return True

    elif state == "waiting_for_subscriber_id":
        val = message.text.strip()
        if not val.isdigit():
            text = "⚠️ **Invalid input.** Please send a valid Telegram User ID (digits only). Send `/cancel` to abort."
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="sub_mgr")]])
            if message_id:
                try:
                    await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=text, reply_markup=markup)
                    return True
                except Exception:
                    pass
            await message.reply_text(text, reply_markup=markup)
            return True
            
        sub_id = int(val)
        first_name = None
        username = None
        try:
            user_obj = await client.get_users(sub_id)
            if user_obj:
                first_name = user_obj.first_name
                username = user_obj.username
        except Exception as e:
            print(f"Failed to fetch user from Telegram API: {e}")
            
        added = await database.add_subscriber(sub_id, first_name, username)
        ADMIN_STATES.pop(user_id, None)
        
        from .ui_admin import show_sub_mgr
        if added:
            text = f"✅ **User `{sub_id}` subscribed successfully!**"
        else:
            text = f"ℹ️ **User `{sub_id}` is already subscribed.**"
            
        if message_id:
            try:
                await message.reply_text(text)
                await show_sub_mgr(client, message.chat.id, message_id)
            except Exception:
                await message.reply_text(text)
        else:
            await message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Subscribers Mgr", callback_data="sub_mgr")]]))
        return True

    elif state == "waiting_for_remove_subscriber_id":
        val = message.text.strip()
        skip = state_data.get("data", {}).get("skip", 0)
        
        if not val.isdigit():
            text = "⚠️ **Invalid input.** Please send a valid Telegram User ID (digits only). Send `/cancel` to abort."
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data=f"remove_subscriber_menu_{skip}")]])
            if message_id:
                try:
                    await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text=text, reply_markup=markup)
                    return True
                except Exception:
                    pass
            await message.reply_text(text, reply_markup=markup)
            return True
            
        sub_id = int(val)
        removed = await database.remove_subscriber(sub_id)
        ADMIN_STATES.pop(user_id, None)
        
        from .ui_admin import show_sub_mgr
        if removed:
            text = f"✅ **User `{sub_id}` unsubscribed and removed successfully!**"
        else:
            text = f"❌ **User `{sub_id}` was not found in the subscriber list.**"
            
        if message_id:
            try:
                await message.reply_text(text)
                await show_sub_mgr(client, message.chat.id, message_id)
            except Exception:
                await message.reply_text(text)
        else:
            await message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Subscribers Mgr", callback_data="sub_mgr")]]))
        return True

    elif state == "waiting_for_subscription_db_url":
        url_input = message.text.strip()
        ADMIN_STATES.pop(user_id, None)
        
        from .ui_admin import show_premium_users_panel
        
        if url_input.lower() in ("none", "default"):
            await database.update_settings({"subscription_db_url": None})
            text = "✅ **Custom Premium Database URL cleared!** Reverted to using sibling Bot .env defaults."
        elif not url_input.startswith("postgresql://") and not url_input.startswith("postgres://"):
            text = "❌ **Invalid Database Connection URL.** It must start with `postgresql://` or `postgres://`.\nReverted or no changes made."
            if message_id:
                try:
                    await client.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=message_id,
                        text=text,
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Premium Panel", callback_data="premium_users_panel")]])
                    )
                    return True
                except Exception:
                    pass
            await message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Premium Panel", callback_data="premium_users_panel")]]))
            return True
        else:
            await database.update_settings({"subscription_db_url": url_input})
            text = "✅ **Custom Premium Database URL configured and saved!**"

        if message_id:
            try:
                await message.reply_text(text)
                await show_premium_users_panel(client, message.chat.id, message_id)
            except Exception:
                await message.reply_text(text)
        else:
            await message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Premium Panel", callback_data="premium_users_panel")]]))
        return True

    elif state == "waiting_for_more_info_msg":
        msg_input = message.text.strip()
        ADMIN_STATES.pop(user_id, None)
        
        if msg_input.lower() in ("none", "default"):
            await database.update_settings({"more_info_msg": None})
            text = "✅ **Guidance / Info message template reverted to default dynamic template!**"
        else:
            await database.update_settings({"more_info_msg": msg_input})
            text = "✅ **Guidance / Info message template updated and saved successfully!**"

        if message_id:
            try:
                await message.reply_text(text)
                from .callbacks_admin import handle_admin_callbacks
                # We can call handle_admin_callbacks with "admin_settings" to show the admin settings panel
                class DummyCallback:
                    def __init__(self, client, chat_id, message_id, from_user):
                        self.message = DummyMessage(chat_id, message_id)
                        self.from_user = from_user
                        self.data = "admin_settings"
                    async def answer(self, *args, **kwargs):
                        pass
                class DummyMessage:
                    def __init__(self, chat_id, message_id):
                        self.chat = DummyChat(chat_id)
                        self.id = message_id
                    async def edit_text(self, *args, **kwargs):
                        return await client.edit_message_text(chat_id=self.chat.id, message_id=self.id, *args, **kwargs)
                class DummyChat:
                    def __init__(self, chat_id):
                        self.id = chat_id
                await handle_admin_callbacks(client, DummyCallback(client, message.chat.id, message_id, message.from_user), "admin_settings")
            except Exception:
                await message.reply_text(text)
        else:
            await message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin Settings", callback_data="admin_settings")]]))
        return True

    return False
