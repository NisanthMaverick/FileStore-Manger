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
    total_users = await database.get_user_count()
    sub_count = await database.get_subscriber_count()
    premium_count = await database.get_premium_cache_count()
    settings = await database.get_settings()
    
    access_status = "Enabled 🔓" if settings.get("access_to_all", True) else "Disabled (Restricted to Subscribers) 🔒"
    testing_mode_status = "Enabled 🧪 (Premium access blocked)" if settings.get("testing_mode", False) else "Disabled ❌"
    
    text = f"👥 **User & Subscribers Management**\n\n" \
           f"📈 **Total Users (database):** `{total_users}`\n" \
           f"⭐ **Subscribed Users:** `{sub_count}`\n" \
           f"💎 **Premium Users (Cached):** `{premium_count}`\n" \
           f"🔓 **Clone Bot Access Mode:** `{access_status}`\n" \
           f"🧪 **Testing Mode Status:** `{testing_mode_status}`\n\n" \
           f"Select an option below to manage subscribers and access permissions:"
           
    toggle_text = "🔒 Restrict Access" if settings.get("access_to_all", True) else "🔓 Enable Access"
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Subscribe User", callback_data="add_subscriber"),
            InlineKeyboardButton("🗑 Remove Subscriber", callback_data="remove_subscriber_menu_0")
        ],
        [
            InlineKeyboardButton("💎 Premium Panel", callback_data="premium_users_panel"),
            InlineKeyboardButton(toggle_text, callback_data="toggle_access_to_all")
        ],
        [
            InlineKeyboardButton("📢 Broadcast Msg", callback_data="broadcast_subs"),
            InlineKeyboardButton("🔙 Back", callback_data="main_panel")
        ]
    ])
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    except Exception as e:
        print(f"Error rendering sub_mgr: {e}")

async def show_premium_users_panel(client: Client, chat_id: int, message_id: int):
    premium_count = await database.get_premium_cache_count()
    settings = await database.get_settings()
    testing_mode_status = "Enabled 🧪 (Premium access blocked)" if settings.get("testing_mode", False) else "Disabled ❌ (Premium access allowed)"
    
    db_url = settings.get("subscription_db_url")
    if db_url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(db_url)
            db_display = f"{parsed.scheme}://{parsed.hostname or 'unknown'}/{parsed.path.lstrip('/')}"
        except Exception:
            db_display = "Set (custom connection URL)"
    else:
        db_display = "Not set (using sibling bot .env default)"

    text = "💎 **Premium Users Control Panel**\n\n" \
           "This bot integrates with the Subscription Bot. Users with plan 1 or 3 are premium users.\n\n" \
           f"💎 **Total Active Cached Premium Users:** `{premium_count}`\n" \
           f"🔌 **Dynamic Premium DB:** `{db_display}`\n" \
           f"🧪 **Testing Mode:** {testing_mode_status}\n\n" \
           "Select an option below:"
           
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Sync Premium", callback_data="sync_premium_users"),
            InlineKeyboardButton("🧪 Toggle Testing", callback_data="toggle_testing_mode")
        ],
        [
            InlineKeyboardButton("🔌 Db Config", callback_data="config_subscription_db_url"),
            InlineKeyboardButton("🔙 Back", callback_data="sub_mgr")
        ]
    ])
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    except Exception as e:
        print(f"Error rendering premium_users_panel: {e}")


async def show_remove_subscriber_menu(client: Client, chat_id: int, message_id: int, skip: int = 0):
    subs, total = await database.list_subscribers(skip=skip, limit=5)
    
    text = f"🗑 **Remove Subscriber / Subscriptions List** (Total: {total})\n\n" \
           "To remove a subscriber, click their delete button below.\n" \
           "You can also directly send the Telegram User ID of the user you want to remove.\n\n"
           
    buttons = []
    if not subs:
        text += "_No subscribed users found._"
    else:
        for s in subs:
            name = s["first_name"] or "Unknown"
            username_str = f" (@{s['username']})" if s["username"] else ""
            text += f"▪️ **{name}**{username_str}\n  ID: `{s['user_id']}`\n\n"
            buttons.append([
                InlineKeyboardButton(f"🗑 Remove {name[:15]}...", callback_data=f"del_sub_{s['user_id']}_{skip}")
            ])
            
    pag_row = []
    if skip > 0:
        pag_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"remove_subscriber_menu_{max(0, skip - 5)}"))
    if skip + 5 < total:
        pag_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"remove_subscriber_menu_{skip + 5}"))
    if pag_row:
        buttons.append(pag_row)
        
    buttons.append([InlineKeyboardButton("🔙 Back to Subscribers Mgr", callback_data="sub_mgr")])
    
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        print(f"Error rendering remove_subscriber_menu: {e}")

async def show_lock_settings(client: Client, chat_id: int, message_id: int):
    settings = await database.get_settings()
    lock_status = "Enabled ✅" if settings.get("lock_buttons_enabled") else "Disabled ❌"
    active_enabled = settings.get("lock_active_series_enabled", False)
    active_status = "Enabled ✅" if active_enabled else "Disabled ❌"
    old_status = "Enabled ✅" if settings.get("lock_old_series_enabled", True) else "Disabled ❌"
    
    if active_enabled:
        day_based_status = "Enabled ✅" if settings.get("lock_day_based_enabled", False) else "Disabled ❌"
        window = settings.get("lock_time_window", 0)
        if window == 0:
            duration_str = "Disabled (Latest only) ❌"
        elif window % 24 == 0:
            days = window // 24
            duration_str = f"{days} day(s) ✅"
        else:
            duration_str = f"{window} hour(s) ✅"
    else:
        day_based_status = "Inactive (Requires Lock Active Series ON) ⚠️"
        duration_str = "Inactive (Requires Lock Active Series ON) ⚠️"
        
    text = (
        "🔒 **Lock Buttons Settings**\n\n"
        f"⚡ **Lock Buttons Master Switch:** {lock_status}\n"
        f"🎬 **Lock Active Series:** {active_status}\n"
        f"⏳ **Lock Old/Non-Active Series:** {old_status}\n"
        f"⏱ **Day-Based Lock for Active Series:** {day_based_status}\n"
        f"📅 **Active Series Unlock Duration:** `{duration_str}`\n\n"
        "**Access Control Logic:**\n"
        "• Master Switch must be enabled for any locks to apply.\n"
        "• If Lock Active Series is enabled, files in active series are locked. If Day-Based Lock is ON, they unlock within the duration window; otherwise, only the latest section is unlocked.\n"
        "• If Lock Old Series is enabled, all non-active series folders are restricted to premium."
    )
    
    toggle_btn_text = "🔴 Disable Master Switch" if settings.get("lock_buttons_enabled") else "🟢 Enable Master Switch"
    active_btn_text = "🎬 Lock Active: ON" if settings.get("lock_active_series_enabled", False) else "🎬 Lock Active: OFF"
    old_btn_text = "⏳ Lock Old: ON" if settings.get("lock_old_series_enabled", True) else "⏳ Lock Old: OFF"
    day_based_btn_text = "⏱ Day-Based: ON" if settings.get("lock_day_based_enabled", False) else "⏱ Day-Based: OFF"
    
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(toggle_btn_text, callback_data="toggle_lock_buttons"),
            InlineKeyboardButton(old_btn_text, callback_data="toggle_lock_old")
        ],
        [
            InlineKeyboardButton(active_btn_text, callback_data="toggle_lock_active"),
            InlineKeyboardButton(day_based_btn_text, callback_data="toggle_lock_day_based")
        ],
        [
            InlineKeyboardButton("📅 Edit Duration", callback_data="edit_unlock_duration"),
            InlineKeyboardButton("📁 Config Active List", callback_data="config_active_series_0")
        ],
        [
            InlineKeyboardButton("ℹ️ Config Info Msg", callback_data="edit_more_info_msg"),
            InlineKeyboardButton("🔙 Back Settings", callback_data="admin_settings")
        ]
    ])
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    except Exception as e:
        print(f"Error rendering lock_settings: {e}")

async def show_active_series_config(client: Client, chat_id: int, message_id: int, skip: int = 0):
    series_list = await database.list_series()
    limit = 5
    
    text = (
        "🎬 **Configure Active Series**\n\n"
        "Select active/inactive series. Non-active series are locked for non-premium users.\n\n"
        "• ✅ = Active (open to everyone)\n"
        "• ❌ = Inactive (restricted to premium/subscribers)\n\n"
        "Click on any series below to toggle active status:"
    )
    
    buttons = []
    sliced_list = series_list[skip:skip+limit]
    
    for s in sliced_list:
        status_emoji = "✅" if s.get("is_active", True) else "❌"
        buttons.append([
            InlineKeyboardButton(f"{status_emoji} {s['title']}", callback_data=f"toggle_series_active_{s['id']}_{skip}")
        ])
        
    pag_row = []
    if skip > 0:
        pag_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"config_active_series_{max(0, skip - limit)}"))
    if skip + limit < len(series_list):
        pag_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"config_active_series_{skip + limit}"))
    if pag_row:
        buttons.append(pag_row)
        
    buttons.append([InlineKeyboardButton("🔙 Back to Lock Settings", callback_data="lock_settings")])
    
    markup = InlineKeyboardMarkup(buttons)
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    except Exception as e:
        print(f"Error rendering active_series_config: {e}")
