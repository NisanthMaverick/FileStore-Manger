from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import database
from config import OWNER_ID

async def show_db_sync(client: Client, chat_id: int, message_id: int):
    settings = await database.get_settings()
    db_channel = settings.get("db_channel_id") or "_Not configured_"
    log_channel = settings.get("log_channel_id") or "_Not configured_"
    db_upload_delay = settings.get("db_upload_delay", 3)
    
    text = f"🔄 **Database Sync & Integrity Engine**\n\n" \
           f"📁 **Storage Channel:** `{db_channel}`\n" \
           f"📝 **Audit Log Channel:** `{log_channel}`\n" \
           f"⏱ **DB Upload Delay:** `{db_upload_delay}` second(s)\n\n" \
           f"Manage connection bindings and scan file indices consistency."
    
    db_btn_text = "📁 Edit/Remove Storage Channel" if settings.get("db_channel_id") else "📁 Configure Storage Channel"
    db_btn_cb = "db_channel_options" if settings.get("db_channel_id") else "edit_db_channel"
    
    log_btn_text = "📝 Edit/Remove Audit Channel" if settings.get("log_channel_id") else "📝 Configure Audit Channel"
    log_btn_cb = "log_channel_options" if settings.get("log_channel_id") else "edit_log_channel"
    
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(db_btn_text, callback_data=db_btn_cb),
            InlineKeyboardButton(log_btn_text, callback_data=log_btn_cb)
        ],
        [
            InlineKeyboardButton("🔄 Run File Integrity Scan", callback_data="run_integrity"),
            InlineKeyboardButton("⏱ DB Upload Delay", callback_data="edit_db_upload_delay")
        ],
        [
            InlineKeyboardButton("⚡ Restart DB", callback_data="restart_db_conn"),
            InlineKeyboardButton("📥 Backup & Data", callback_data="backup_menu")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="main_panel")
        ]
    ])
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    except Exception as e:
        print(f"Error rendering db_sync: {e}")

async def show_backup_menu(client: Client, chat_id: int, message_id: int):
    text = (
        "📥 **Backup & Database Management**\n\n"
        "Here you can export all settings, files, and users to a JSON backup file, "
        "or upload a backup to restore all data.\n\n"
        "Select an action below:"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📤 Export JSON Backup", callback_data="export_db_backup"),
            InlineKeyboardButton("📥 Import JSON Backup", callback_data="import_db_backup")
        ],
        [
            InlineKeyboardButton("🔙 Back to Database Engine", callback_data="db_sync")
        ]
    ])
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    except Exception as e:
        print(f"Error rendering backup_menu: {e}")

async def show_manage_clones(client: Client, chat_id: int, message_id: int):
    bots = await database.get_clone_bots()
    settings = await database.get_settings()
    primary = settings.get("primary_clone_username")
    
    text = "🤖 **Clone Bot Instances** (Max: 2)\n\n"
    if not bots:
        text += "_No clone bots added yet._"
    else:
        for idx, b in enumerate(bots):
            status_str = "Active 🟢" if b["is_active"] else "Inactive 🔴"
            primary_str = " (⭐ Primary Redirection)" if b["username"] == primary else ""
            text += f"**{idx+1}. {b['name']}** (@{b['username']})\n" \
                    f"⚡ Status: {status_str}{primary_str}\n\n"
    
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=get_manage_clones_markup(bots, primary))
    except Exception as e:
        print(f"Error rendering manage_clones: {e}")

async def show_mgr_admins(client: Client, chat_id: int, message_id: int):
    text = f"🛡️ **Administrators List**\n\n" \
           f"Master Owner: `{OWNER_ID}`\n\n" \
           f"Here you can add or remove users by Telegram User ID to give them access to this admin panel."
    
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add Admin ID", callback_data="add_admin_id"),
            InlineKeyboardButton("🗑 Remove Admin ID", callback_data="remove_admin_id")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="admin_settings")
        ]
    ])
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    except Exception as e:
        print(f"Error rendering mgr_admins: {e}")

def get_manage_clones_markup(bots, primary):
    buttons = []
    for b in bots:
        buttons.append([
            InlineKeyboardButton(f"🤖 {b['name']} (@{b['username']})", callback_data=f"bot_details_{b['username']}")
        ])
    if len(bots) < 2:
        buttons.append([
            InlineKeyboardButton("➕ Register New Token", callback_data="add_clone")
        ])
    buttons.append([
        InlineKeyboardButton("🔙 Back", callback_data="admin_settings")
    ])
    return InlineKeyboardMarkup(buttons)

def get_bot_details_markup(bot, primary):
    buttons = []
    status_action = "Stop Instance 🔴" if bot["is_active"] else "Start Instance 🟢"
    buttons.append([
        InlineKeyboardButton(f"{status_action}", callback_data=f"status_bot_{bot['username']}"),
        InlineKeyboardButton("🗑 Destroy Instance", callback_data=f"del_bot_{bot['username']}")
    ])
    if bot["is_active"] and bot["username"] != primary:
        buttons.append([
            InlineKeyboardButton("⭐ Promote to Redirection", callback_data=f"primary_bot_{bot['username']}")
        ])
    buttons.append([
        InlineKeyboardButton("🔙 Back", callback_data="manage_clones")
    ])
    return InlineKeyboardMarkup(buttons)

async def show_bot_details(client: Client, chat_id: int, message_id: int, bot: dict, primary: str):
    status_str = "Active 🟢" if bot["is_active"] else "Inactive 🔴"
    primary_label = " (⭐ Primary Redirect)" if bot["username"] == primary else ""
    text = f"🤖 **Clone Bot Instance Details**\n\n" \
           f"👤 **Name:** {bot['name']}\n" \
           f"🤖 **Username:** @{bot['username']}\n" \
           f"⚡ **Status:** {status_str}{primary_label}\n\n" \
           f"Manage this bot instance using the controls below:"
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=get_bot_details_markup(bot, primary))
    except Exception as e:
        print(f"Error rendering bot_details: {e}")

async def show_sub_mgr(client: Client, chat_id: int, message_id: int):
    count = await database.get_user_count()
    text = f"👥 **User & Subscribers Management**\n\n" \
           f"📈 **Total Subscribers:** `{count}`\n\n" \
           f"Select an option below to interact with subscribers:"
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 Broadcast Message", callback_data="broadcast_subs")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="main_panel")
        ]
    ])
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    except Exception as e:
        print(f"Error rendering sub_mgr: {e}")
