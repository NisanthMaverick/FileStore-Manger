import asyncio
from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import database
from .helpers import ACTIVE_CLONES
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
            try:
                await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
            except Exception:
                await client.send_message(chat_id=chat_id, text=text, reply_markup=markup)
        return

    # Check if series is inactive (premium lock) and user is not premium
    from config import OWNER_ID
    if not series.get("is_active", True):
        is_user_premium = await database.is_premium_user(chat_id, OWNER_ID)
        if not is_user_premium:
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
                    InlineKeyboardButton("💳 Buy Subscription", url="https://t.me/SubscriptionTamilan_bot"),
                    InlineKeyboardButton("👨‍💻 Contact Admin", url=contact_url)
                ],
                [
                    InlineKeyboardButton("🔄 Check Subscription", callback_data=f"cl_chk_sub_{series_id}_0")
                ],
                [
                    InlineKeyboardButton("🔙 Back to Categories", callback_data="cl_browse_series_0")
                ]
            ])
            if is_new_message:
                await client.send_message(chat_id=chat_id, text=text, reply_markup=markup)
            else:
                try:
                    await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
                except Exception:
                    await client.send_message(chat_id=chat_id, text=text, reply_markup=markup)
            return


    sections = await database.list_sections(series_id, parent_id=section_id)

    custom_msg = None
    custom_pic = None
    per_row = 2

    if section_id:
        current_sec = await database.get_section(section_id)
        if current_sec:
            custom_msg = current_sec.get("custom_msg")
            custom_pic = current_sec.get("custom_pic")
            per_row = current_sec.get("buttons_per_row", 2)
    else:
        custom_msg = series.get("custom_msg")
        custom_pic = series.get("custom_pic")
        per_row = series.get("buttons_per_row", 2)

    if custom_msg and custom_msg.strip():
        text = custom_msg
    else:
        path_str = f"🎬 **{series['title']}**"
        if section_id:
            sec_path = await database.get_section_path(section_id)
            path_str += f" › {sec_path}"

        text = f"{path_str}\n"
        if series.get('description') and not section_id:
            text += f"_{series['description']}_\n"
        text += "\n"

    buttons = []

    if sections:
        settings = await database.get_settings()
        from config import OWNER_ID
        is_premium = await database.is_premium_user(chat_id, OWNER_ID)


        lock_enabled = settings.get("lock_buttons_enabled", False)
        window = settings.get("lock_time_window", 0)
        latest_file_sec_id = None
        
        if lock_enabled and not is_premium and window == 0:
            file_sections = [sec for sec in sections if sec.get("sec_type") == "files"]
            if file_sections:
                latest_file_sec_id = max(sec["id"] for sec in file_sections)

        row = []
        for s in sections:
            if s.get("sec_type") == "files":
                is_unlocked = True
                if lock_enabled and not is_premium:
                    if window > 0:
                        created_at = s.get("created_at")
                        if created_at:
                            from datetime import datetime
                            age_hours = (datetime.utcnow() - created_at).total_seconds() / 3600.0
                            if age_hours >= window:
                                is_unlocked = False
                    else:
                        if s["id"] != latest_file_sec_id:
                            is_unlocked = False

                if is_unlocked:
                    btn = InlineKeyboardButton(f"📥 {s['name']}", callback_data=f"cl_send_sec_{series_id}_{s['id']}")
                else:
                    btn = InlineKeyboardButton(f"🔒 {s['name']}", callback_data=f"cl_locked_sec_{series_id}_{s['id']}")
            else:
                btn = InlineKeyboardButton(f"📁 {s['name']}", callback_data=f"cl_tree_{series_id}_{s['id']}")
            
            row.append(btn)
            if len(row) == per_row:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
    else:
        if not custom_msg:
            text += "_Nothing here yet._\n"

    if section_id:
        parent_id = current_sec["parent_id"] if current_sec else None
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"cl_tree_{series_id}_{parent_id or 0}")])
    else:
        buttons.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="cl_browse_series_0")])

    markup = InlineKeyboardMarkup(buttons)
    if custom_pic:
        from pyrogram.types import InputMediaPhoto
        if is_new_message:
            try:
                await client.send_photo(chat_id=chat_id, photo=custom_pic, caption=text, reply_markup=markup)
            except Exception as e:
                print(f"Error sending photo in show_user_tree: {e}")
        else:
            try:
                await client.edit_message_media(
                    chat_id=chat_id,
                    message_id=message_id,
                    media=InputMediaPhoto(custom_pic, caption=text),
                    reply_markup=markup
                )
            except Exception:
                try:
                    await client.delete_messages(chat_id=chat_id, message_ids=message_id)
                except Exception:
                    pass
                try:
                    await client.send_photo(chat_id=chat_id, photo=custom_pic, caption=text, reply_markup=markup)
                except Exception as e:
                    print(f"Error sending photo in show_user_tree: {e}")
    else:
        if is_new_message:
            try:
                await client.send_message(chat_id=chat_id, text=text, reply_markup=markup)
            except Exception as e:
                print(f"Error sending text in show_user_tree: {e}")
        else:
            try:
                await client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=markup
                )
            except Exception:
                try:
                    await client.delete_messages(chat_id=chat_id, message_ids=message_id)
                except Exception:
                    pass
                try:
                    await client.send_message(chat_id=chat_id, text=text, reply_markup=markup)
                except Exception as e:
                    print(f"Error sending text in show_user_tree: {e}")
