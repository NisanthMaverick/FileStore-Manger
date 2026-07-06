import asyncio
from pyrogram import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import database
from .helpers import (
    check_user_subscribed, get_clone_welcome_markup,
    handle_auto_delete_if_enabled, log_download_action,
    copy_messages_with_start_end, check_clone_access, handle_clone_callback_access_denied,
    SENDING_USERS
)
from .tree import show_user_tree
from .handlers import handle_payload
from config import OWNER_ID

async def clone_callback_handler(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in SENDING_USERS:
        return await callback.answer("⚠️ Your series is sending. Once complete all files, try a new file.", show_alert=True)
    if not await check_clone_access(user_id):
        await handle_clone_callback_access_denied(client, callback)
        return
    data = callback.data

    if data.startswith("fsub_ref_"):
        is_subbed, invite_buttons = await check_user_subscribed(client, user_id)
        if not is_subbed:
            return await callback.answer("Yᴏᴜ ᴀʀᴇ ɴᴏᴛ ʏᴇᴛ ᴊᴏɪɴᴇᴅ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ. \nFɪʀsᴛ ᴊᴏɪɴ ᴀɴᴅ ᴛʜᴇɴ ᴘʀᴇss ʀᴇғʀᴇsʜ ʙᴜᴛᴛᴏɴ 🤤", show_alert=True)

        payload = data.replace("fsub_ref_", "")
        if payload == "home":
            payload = ""

        await callback.answer("Verification successful! Delivering...")
        await callback.message.delete()
        
        fake_message = callback.message
        fake_message.from_user = callback.from_user
        await handle_payload(client, fake_message, payload)

    elif data.startswith("cl_series_"):
        series_id = int(data.split("_")[2])
        series = await database.get_series(series_id)
        if series:
            journey = None
            if series.get("journey_id"):
                journey = await database.get_journey(series["journey_id"])
            if not journey:
                journey = {
                    "lock_buttons_enabled": False,
                    "lock_active_series_enabled": False,
                    "lock_old_series_enabled": True,
                    "lock_day_based_enabled": False,
                    "lock_time_window": 0,
                    "lock_individual_enabled": False
                }
            
            is_locked = False
            if journey.get("lock_buttons_enabled", False):
                if not series.get("is_active", True) and journey.get("lock_old_series_enabled", True):
                    is_locked = True
                elif journey.get("lock_individual_enabled", False) and series.get("is_locked", False):
                    is_locked = True
            
            if is_locked:
                is_user_premium = await database.is_premium_user(user_id, OWNER_ID)
                if not is_user_premium:
                    await callback.answer("🔒 This series is restricted to premium users.", show_alert=True)
                    owner_username = None
                    try:
                        owner_user = await client.get_users(OWNER_ID)
                        if owner_user and owner_user.username:
                            owner_username = owner_user.username
                    except Exception:
                        pass
                    contact_url = f"https://t.me/{owner_username}" if owner_username else f"tg://user?id={OWNER_ID}"
                    
                    text = (
                        "🔒 **Premium Access Required**\n\n"
                        "You are not a premium user to see old series/content.\n"
                        "Please buy a subscription or contact the administrator if you have any issues."
                    )
                    markup = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("💳 Buy Subscription", url="https://t.me/SubscriptionTamilan_bot?start=plans"),
                            InlineKeyboardButton("👨‍💻 Contact Admin", url=contact_url)
                        ],
                        [
                            InlineKeyboardButton("🔄 Check Subscription", callback_data=f"cl_chk_sub_{series_id}_0")
                        ],
                        [
                            InlineKeyboardButton("🔙 Back to Categories", callback_data=f"cl_journey_{series['journey_id'] or 0}_0")
                        ]
                    ])
                    await callback.message.edit_text(text, reply_markup=markup)
                    return

        await callback.answer()
        await show_user_tree(client, callback.message.chat.id, callback.message.id, series_id, section_id=None)

    elif data.startswith("cl_tree_"):
        parts = data.split("_")
        series_id = int(parts[2])
        section_id = int(parts[3])

        if section_id > 0:
            sec = await database.get_section(section_id)
            if sec and sec.get("sec_type") == "files":
                settings = await database.get_settings()
                db_channel = settings.get("db_channel_id")
                
                series = await database.get_series(series_id)
                if series and series.get("journey_id"):
                    journey = await database.get_journey(series["journey_id"])
                    if journey and journey.get("db_channel_id"):
                        db_channel = journey["db_channel_id"]
                        
                if not db_channel:
                    return await callback.answer("Storage channel not configured.", show_alert=True)
                files, total_files = await database.list_files(skip=0, limit=500, series_id=series_id, section_id=section_id)
                if not files:
                    return await callback.answer("No files in this section yet.", show_alert=True)
                await callback.answer(f"⏳ Sending {total_files} file(s)...")
                
                file_msg_ids = [f["message_id"] for f in files]
                sent_msg_ids = await copy_messages_with_start_end(client, user_id, db_channel, file_msg_ids)
                
                if sent_msg_ids:
                    await handle_auto_delete_if_enabled(client, user_id, sent_msg_ids)
                return

        await callback.answer()
        await show_user_tree(client, callback.message.chat.id, callback.message.id, series_id, section_id=section_id if section_id > 0 else None)

    elif data.startswith("cl_send_sec_"):
        parts = data.split("_")
        series_id = int(parts[3])
        section_id = int(parts[4])

        settings = await database.get_settings()
        db_channel = settings.get("db_channel_id")
        
        series = await database.get_series(series_id)
        if series and series.get("journey_id"):
            journey = await database.get_journey(series["journey_id"])
            if journey and journey.get("db_channel_id"):
                db_channel = journey["db_channel_id"]
                
        if not db_channel:
            return await callback.answer("Storage channel not configured.", show_alert=True)

        files, total_files = await database.list_files(skip=0, limit=500, series_id=series_id, section_id=section_id)
        if not files:
            return await callback.answer("No files found in this section.", show_alert=True)

        await callback.answer(f"⏳ Sending {total_files} file(s)...")

        file_msg_ids = [f["message_id"] for f in files]
        sent_msg_ids = await copy_messages_with_start_end(client, user_id, db_channel, file_msg_ids)
        
        if sent_msg_ids:
            await handle_auto_delete_if_enabled(client, user_id, sent_msg_ids)

        try:
            fake_msg = callback.message
            fake_msg.from_user = callback.from_user
            await log_download_action(client, files[0], fake_msg)
        except Exception:
            pass

    elif data.startswith("get_ep_"):
        file_code = data.split("_")[2]
        file_info = await database.get_file(file_code)
        if not file_info:
            return await callback.answer("File not found or deleted.", show_alert=True)

        settings = await database.get_settings()
        db_channel = settings.get("db_channel_id")
        if not db_channel:
            return await callback.answer("Storage channel not configured by admin.", show_alert=True)

        series = None
        journey = None
        if file_info.get("series_id"):
            series = await database.get_series(file_info["series_id"])
            if series and series.get("journey_id"):
                journey = await database.get_journey(series["journey_id"])
                
        if not journey:
            journey = {
                "lock_buttons_enabled": False,
                "lock_active_series_enabled": False,
                "lock_old_series_enabled": True,
                "lock_day_based_enabled": False,
                "lock_time_window": 0,
                "lock_individual_enabled": False
            }

        if journey.get("lock_buttons_enabled"):
            is_user_premium = await database.is_premium_user(user_id, OWNER_ID)
            
            if not is_user_premium:
                is_locked = False
                
                # Check individual locks
                if journey.get("lock_individual_enabled", False):
                    if series and series.get("is_locked", False):
                        is_locked = True
                    elif file_info.get("section_id"):
                        sec = await database.get_section(file_info["section_id"])
                        if sec and sec.get("is_locked", False):
                            is_locked = True
                            
                if not is_locked:
                    parent_series_active = series.get("is_active", True) if series else True
                    if not parent_series_active:
                        if journey.get("lock_old_series_enabled", True):
                            is_locked = True
                    else:
                        if journey.get("lock_active_series_enabled", False):
                            if journey.get("lock_day_based_enabled", False):
                                window = journey.get("lock_time_window", 0)
                                is_within_window = False
                                if file_info.get("section_id"):
                                    sec = await database.get_section(file_info["section_id"])
                                    if sec and window > 0 and sec.get("created_at"):
                                        from datetime import datetime
                                        age_hours = (datetime.utcnow() - sec["created_at"]).total_seconds() / 3600.0
                                        if age_hours < window:
                                            is_within_window = True
                                
                                if not is_within_window:
                                    is_locked = True
                            else:
                                files, total = await database.list_files(skip=0, limit=1000, series_id=file_info.get("series_id"), section_id=file_info.get("section_id"))
                                if files:
                                    latest_file = max(files, key=lambda f: f["message_id"])
                                    if file_info["file_code"] != latest_file["file_code"]:
                                        is_locked = True
                                        
                if is_locked:
                    return await callback.answer("🔒 You are not a premium user, only premium users can access old files.", show_alert=True)

        await callback.answer("Delivering episode...")
        try:
            sent_msg_ids = await copy_messages_with_start_end(client, user_id, db_channel, [file_info["message_id"]])
            if sent_msg_ids:
                await handle_auto_delete_if_enabled(client, user_id, sent_msg_ids)
            
            fake_msg = callback.message
            fake_msg.from_user = callback.from_user
            await log_download_action(client, file_info, fake_msg)
        except Exception as e:
            print(f"Failed to copy file message: {e}")
            await callback.message.reply_text("❌ Failed to deliver file. Please contact bot admin.")

    elif data.startswith("cl_browse_series_"):
        skip = int(data.split("_")[3])
        await callback.answer()
        
        settings, journeys, is_user_premium = await asyncio.gather(
            database.get_settings(),
            database.list_journeys(),
            database.is_premium_user(user_id, OWNER_ID)
        )

        limit = settings.get("series_buttons_per_page", 5)
        library_msg = settings.get("series_library_custom_msg")
        header = "🗺️ **Home**\n━━━━━━━━━━━━━━━━━━━━\n\nSelect a category/journey to explore:\n\n"
        if library_msg:
            text = f"{library_msg}\n\n{header}"
        else:
            text = header
            
        buttons = []
        
        sliced_list = journeys[skip:skip+limit]
        if not sliced_list:
            text += "_No journeys available._"
        else:
            row = []
            for j in sliced_list:
                text += f"▪️ **{j['name']}**\n"
                is_j_locked = j.get("is_locked", False) and not is_user_premium
                if is_j_locked:
                    row.append(InlineKeyboardButton(f"🔒 {j['name']}", callback_data=f"cl_journey_{j['id']}_0"))
                else:
                    row.append(InlineKeyboardButton(f"🗺️ View {j['name']}", callback_data=f"cl_journey_{j['id']}_0"))
                if len(row) == 2:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
        
        pag_row = []
        if skip > 0:
            pag_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"cl_browse_series_{max(0, skip - limit)}"))
        if skip + limit < len(journeys):
            pag_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"cl_browse_series_{skip + limit}"))
        if pag_row:
            buttons.append(pag_row)
            
        buttons.append([InlineKeyboardButton("🔙 Back Home", callback_data="cl_welcome_home")])
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
 
    elif data.startswith("cl_journey_"):
        parts = data.split("_")
        journey_id = int(parts[2])
        skip = int(parts[3])
        await callback.answer()
        
        journey, settings, series_list, is_user_premium = await asyncio.gather(
            database.get_journey(journey_id),
            database.get_settings(),
            database.list_series(journey_id=journey_id),
            database.is_premium_user(user_id, OWNER_ID)
        )
        
        if not journey:
            return await callback.message.edit_text("❌ Category not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Categories", callback_data="cl_browse_series_0")]]))
            
        if journey.get("is_locked", False) and not is_user_premium:
            owner_username = None
            try:
                owner_user = await client.get_users(OWNER_ID)
                if owner_user and owner_user.username:
                    owner_username = owner_user.username
            except Exception:
                pass
            contact_url = f"https://t.me/{owner_username}" if owner_username else f"tg://user?id={OWNER_ID}"
            
            text = (
                f"🔒 **Premium Access Required — {journey['name']}**\n\n"
                "This category is restricted to premium users.\n"
                "Please buy a subscription or contact the administrator if you have any issues."
            )
            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("💳 Buy Subscription", url="https://t.me/SubscriptionTamilan_bot?start=plans"),
                    InlineKeyboardButton("👨‍💻 Contact Admin", url=contact_url)
                ],
                [
                    InlineKeyboardButton("🔄 Check Subscription", callback_data=f"cl_chk_j_sub_{journey_id}")
                ],
                [
                    InlineKeyboardButton("🔙 Back to Categories", callback_data="cl_browse_series_0")
                ]
            ])
            await callback.message.edit_text(text, reply_markup=markup)
            return

        limit = settings.get("series_buttons_per_page", 5)
        text = f"🗺️ **Home › {journey['name']}**\n━━━━━━━━━━━━━━━━━━━━\n\n📁 Go inside {journey['name']} to browse series:\n\n"
        buttons = []
        
        sliced_list = series_list[skip:skip+limit]
        if not sliced_list:
            text += "_No series available in this category._"
        else:
            row = []
            for s in sliced_list:
                text += f"▪️ **{s['title']}**\n"
                is_series_unlocked = s.get("is_active", True) or is_user_premium
                if journey.get("is_locked", False):
                    is_series_unlocked = is_user_premium
                elif journey["lock_buttons_enabled"] and journey["lock_individual_enabled"] and s.get("is_locked", False):
                    is_series_unlocked = is_user_premium
                    
                if is_series_unlocked:
                    btn = InlineKeyboardButton(f"🎬 {s['title']}", callback_data=f"cl_series_{s['id']}_0")
                else:
                    btn = InlineKeyboardButton(f"🔒 {s['title']}", callback_data=f"cl_series_{s['id']}_0")
                row.append(btn)
                if len(row) == 2:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
                    
        pag_row = []
        if skip > 0:
            pag_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"cl_journey_{journey_id}_{max(0, skip - limit)}"))
        if skip + limit < len(series_list):
            pag_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"cl_journey_{journey_id}_{skip + limit}"))
        if pag_row:
            buttons.append(pag_row)
            
        buttons.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="cl_browse_series_0")])
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "cl_welcome_home":
        await callback.answer()
        settings = await database.get_settings()
        welcome_text = settings.get("welcome_msg") or "Hey {mention}, welcome to {bot_name}!"
        welcome_text = welcome_text.format(
            mention=callback.from_user.mention,
            first_name=callback.from_user.first_name,
            bot_name=client.me.first_name,
            bot_link=f"https://t.me/{client.me.username}",
            mention_bot=f"[{client.me.first_name}](tg://user?id={client.me.id})",
            mentionbot=f"[{client.me.first_name}](tg://user?id={client.me.id})"
        )
        markup = get_clone_welcome_markup(settings.get("custom_buttons", "[]"))
        
        full_markup = []
        if markup:
            full_markup = list(markup.inline_keyboard)
        full_markup.append([InlineKeyboardButton("🎬 Browse Series / Categories", callback_data="cl_browse_series_0")])
        full_markup.append([InlineKeyboardButton("ℹ️ Info", callback_data="cl_user_more_info")])
        
        await callback.message.edit_text(welcome_text, reply_markup=InlineKeyboardMarkup(full_markup))

    elif data == "cl_user_more_info":
        await callback.answer()
        settings = await database.get_settings()
        info_text = await database.get_formatted_more_info_msg(settings)
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back Home", callback_data="cl_welcome_home")]])
        await callback.message.edit_text(info_text, reply_markup=markup)

    elif data.startswith("cl_locked_sec_"):
        parts = data.split("_")
        series_id = int(parts[3])
        sec_id = int(parts[4])
        
        sec = await database.get_section(sec_id)
        parent_id = sec["parent_id"] if sec else None
        
        owner_username = None
        try:
            owner_user = await client.get_users(OWNER_ID)
            if owner_user and owner_user.username:
                owner_username = owner_user.username
        except Exception:
            pass
        contact_url = f"https://t.me/{owner_username}" if owner_username else f"tg://user?id={OWNER_ID}"
        
        text = (
            "🔒 **Premium Access Required**\n\n"
            "You are not a premium user to see old files/episodes.\n"
            "Please buy a subscription or contact the administrator if you have any issues."
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💳 Buy Subscription", url="https://t.me/SubscriptionTamilan_bot?start=plans"),
                InlineKeyboardButton("👨‍💻 Contact Admin", url=contact_url)
            ],
            [
                InlineKeyboardButton("🔄 Check Subscription", callback_data=f"cl_chk_sub_{series_id}_{sec_id}")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data=f"cl_tree_{series_id}_{parent_id or 0}")
            ]
        ])
        await callback.message.edit_text(text, reply_markup=markup)

    elif data.startswith("cl_chk_sub_"):
        parts = data.split("_")
        series_id = int(parts[3])
        sec_id = int(parts[4])
        
        await callback.answer("🔄 Checking subscription status...", show_alert=False)
        is_now_premium = await database.sync_single_premium_user(user_id)
        
        if is_now_premium:
            await callback.answer("✅ Verification successful! You are now premium.", show_alert=True)
            if sec_id > 0:
                # If this section is a files-type, send files directly (not the tree which shows empty)
                sec = await database.get_section(sec_id)
                if sec and sec.get("sec_type") == "files":
                    settings = await database.get_settings()
                    db_channel = settings.get("db_channel_id")
                    
                    series = await database.get_series(series_id)
                    if series and series.get("journey_id"):
                        journey = await database.get_journey(series["journey_id"])
                        if journey and journey.get("db_channel_id"):
                            db_channel = journey["db_channel_id"]
                            
                    if not db_channel:
                        return await callback.answer("Storage channel not configured.", show_alert=True)
                    files, total_files = await database.list_files(skip=0, limit=500, series_id=series_id, section_id=sec_id)
                    if not files:
                        return await callback.answer("No files in this section yet.", show_alert=True)
                    await callback.answer(f"⏳ Sending {total_files} file(s)...")
                    file_msg_ids = [f["message_id"] for f in files]
                    sent_msg_ids = await copy_messages_with_start_end(client, user_id, db_channel, file_msg_ids)
                    if sent_msg_ids:
                        await handle_auto_delete_if_enabled(client, user_id, sent_msg_ids)
                    return
                else:
                    await show_user_tree(client, callback.message.chat.id, callback.message.id, series_id, section_id=sec_id)
            else:
                await show_user_tree(client, callback.message.chat.id, callback.message.id, series_id, section_id=None)
        else:
            await callback.answer("❌ No active premium subscription found for your ID (Plan 1 required).", show_alert=True)

    elif data.startswith("cl_chk_j_sub_"):
        journey_id = int(data.split("_")[4])
        await callback.answer("🔄 Checking subscription status...", show_alert=False)
        is_now_premium = await database.sync_single_premium_user(user_id)
        if is_now_premium:
            await callback.answer("✅ Verification successful! You are now premium.", show_alert=True)
            journey, settings, series_list, is_user_premium = await asyncio.gather(
                database.get_journey(journey_id),
                database.get_settings(),
                database.list_series(journey_id=journey_id),
                database.is_premium_user(user_id, OWNER_ID)
            )
            if journey:
                limit = settings.get("series_buttons_per_page", 5)
                text = f"🗺️ **Home › {journey['name']}**\n━━━━━━━━━━━━━━━━━━━━\n\n📁 Go inside {journey['name']} to browse series:\n\n"
                buttons = []
                sliced_list = series_list[0:limit]
                if not sliced_list:
                    text += "_No series available in this category._"
                else:
                    row = []
                    for s in sliced_list:
                        text += f"▪️ **{s['title']}**\n"
                        is_series_unlocked = s.get("is_active", True) or is_user_premium
                        if journey.get("is_locked", False):
                            is_series_unlocked = is_user_premium
                        elif journey["lock_buttons_enabled"] and journey["lock_individual_enabled"] and s.get("is_locked", False):
                            is_series_unlocked = is_user_premium
                            
                        if is_series_unlocked:
                            btn = InlineKeyboardButton(f"🎬 {s['title']}", callback_data=f"cl_series_{s['id']}_0")
                        else:
                            btn = InlineKeyboardButton(f"🔒 {s['title']}", callback_data=f"cl_series_{s['id']}_0")
                        row.append(btn)
                        if len(row) == 2:
                            buttons.append(row)
                            row = []
                    if row:
                        buttons.append(row)
                pag_row = []
                if limit < len(series_list):
                    pag_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"cl_journey_{journey_id}_{limit}"))
                if pag_row:
                    buttons.append(pag_row)
                buttons.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="cl_browse_series_0")])
                await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await callback.answer("❌ No active premium subscription found for your ID (Plan 1 required).", show_alert=True)

