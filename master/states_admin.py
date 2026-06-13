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
from .ui_admin import show_db_sync, show_mgr_admins

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
        ADMIN_STATES.pop(user_id, None)
        if message_id:
            try:
                await client.edit_message_text(chat_id=message.chat.id, message_id=message_id, text="📢 **Broadcasting message to all subscribers... Please wait.**")
            except Exception:
                pass

        users = await database.list_users(limit=10000)
        success = 0
        failed = 0
        
        for u in users:
            try:
                await message.copy(chat_id=u["user_id"])
                success += 1
                await asyncio.sleep(0.05)
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
                await message.copy(chat_id=u["user_id"])
                success += 1
            except Exception:
                failed += 1

        report_text = f"📢 **Broadcast Completed**\n\n✅ **Success:** {success}\n" \
                      f"❌ **Failed:** {failed}"
        
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

    return False
