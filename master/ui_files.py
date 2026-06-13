from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import database
from .helpers import get_back_button

async def show_folder_management(client: Client, chat_id: int, message_id: int, series_id: int, section_id: int = 0, library_skip: int = 0):
    series = await database.get_series(series_id)
    if not series:
        try:
            await client.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ Series not found.", reply_markup=InlineKeyboardMarkup([get_back_button(f"manage_series_skip_{library_skip}")]))
        except Exception:
            pass
        return

    is_root = (section_id == 0)
    current_sec = None
    if not is_root:
        current_sec = await database.get_section(section_id)
        if not current_sec:
            try:
                await client.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ Folder not found.", reply_markup=InlineKeyboardMarkup([InlineKeyboardButton("🔙 Back to Series", callback_data=f"browse_sec_{series_id}_0_{library_skip}")]))
            except Exception:
                pass
            return

    if is_root:
        name = series["title"]
        custom_msg = series.get("custom_msg")
        buttons_per_row = series.get("buttons_per_row", 2)
        type_str = "Series (Root)"
    else:
        name = current_sec["name"]
        custom_msg = current_sec.get("custom_msg")
        buttons_per_row = current_sec.get("buttons_per_row", 2)
        type_str = "Folder"

    custom_msg_status = custom_msg if custom_msg else "Default (Breadcrumbs / Description)"
    
    text = (
        f"⚙️ **{type_str} Settings: {name}**\n\n"
        f"💬 **Custom Message:**\n`{custom_msg_status}`\n\n"
        f"🔢 **Buttons per Row:** `{buttons_per_row}`\n\n"
        "Configure folder settings or perform administrative actions below:"
    )

    buttons_list = [
        [
            InlineKeyboardButton("💬 Edit Message", callback_data=f"edit_sec_msg_{series_id}_{section_id}_{library_skip}"),
            InlineKeyboardButton("🔢 Buttons Per Row", callback_data=f"edit_sec_cols_{series_id}_{section_id}_{library_skip}")
        ],
        [
            InlineKeyboardButton("✏️ Rename", callback_data=f"rename_series_opt_{series_id}_{library_skip}" if is_root else f"rename_sec_{series_id}_{section_id}_{library_skip}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"tree_del_series_{series_id}_{library_skip}" if is_root else f"tree_del_sec_{series_id}_{section_id}_{library_skip}")
        ]
    ]

    if not is_root:
        buttons_list.append([
            InlineKeyboardButton("📂 Move Folder", callback_data=f"move_folder_select_{series_id}_{section_id}_{library_skip}_0")
        ])

    buttons_list.append([
        InlineKeyboardButton("🔙 Back to Folder", callback_data=f"browse_sec_{series_id}_{section_id}_{library_skip}")
    ])

    markup = InlineKeyboardMarkup(buttons_list)

    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    except Exception as e:
        print(f"Error rendering folder_management: {e}")

async def show_series_browse(client: Client, chat_id: int, message_id: int, series_id: int, section_id: int = None, library_skip: int = 0):
    series = await database.get_series(series_id)
    if not series:
        try:
            await client.edit_message_text(chat_id=chat_id, message_id=message_id, text="Series not found.", reply_markup=InlineKeyboardMarkup([get_back_button(f"manage_series_skip_{library_skip}")]))
        except Exception:
            pass
        return

    current_sec = None
    if section_id:
        current_sec = await database.get_section(section_id)

    sections = await database.list_sections(series_id, parent_id=section_id)

    path_str = f"🎬 **Series:** {series['title']}"
    if section_id:
        sec_path = await database.get_section_path(section_id)
        path_str += f" › {sec_path}"

    text = f"{path_str}\n"
    if series['description'] and not section_id:
        text += f"_{series['description']}_\n"
    text += "\n"

    per_row = 2
    if section_id:
        if current_sec:
            per_row = current_sec.get("buttons_per_row", 2)
    else:
        per_row = series.get("buttons_per_row", 2)

    buttons = []

    if sections:
        row = []
        for s in sections:
            if s.get("sec_type") == "files":
                btn = InlineKeyboardButton(f"📥 {s['name']}", callback_data=f"filesec_act_{series_id}_{s['id']}_{library_skip}")
            else:
                btn = InlineKeyboardButton(f"📁 {s['name']}", callback_data=f"browse_sec_{series_id}_{s['id']}_{library_skip}")
            row.append(btn)
            if len(row) == per_row:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
    else:
        text += "_This folder is empty._\n"

    buttons.append([
        InlineKeyboardButton("➕ Add Button", callback_data=f"tree_add_btn_{series_id}_{section_id or 0}_{library_skip}"),
        InlineKeyboardButton("📦 Bulk Add", callback_data=f"tree_bulk_add_{series_id}_{section_id or 0}_{library_skip}")
    ])
    
    if section_id:
        buttons.append([
            InlineKeyboardButton("⚙️ Folder Management", callback_data=f"manage_folder_opt_{series_id}_{section_id}_{library_skip}")
        ])
    else:
        buttons.append([
            InlineKeyboardButton("⚙️ Series Management", callback_data=f"manage_folder_opt_{series_id}_0_{library_skip}")
        ])

    if section_id:
        parent_id = current_sec["parent_id"] if current_sec else None
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"browse_sec_{series_id}_{parent_id or 0}_{library_skip}")])
    else:
        buttons.append([InlineKeyboardButton("🔙 Back to Series Library", callback_data=f"manage_series_skip_{library_skip}")])

    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        print(f"Error rendering show_series_browse: {e}")

async def show_manage_series(client: Client, chat_id: int, message_id: int, skip: int = 0):
    settings = await database.get_settings()
    limit = settings.get("series_buttons_per_page", 5)
    
    series_list = await database.list_series()
    text = "🎬 **Video Series Library**\n\nSelect a series to browse:\n\n"
    buttons = []
    
    sliced_list = series_list[skip:skip+limit]
    if not sliced_list:
        text += "_No series created yet or page is empty._"
    else:
        for s in sliced_list:
            buttons.append([
                InlineKeyboardButton(f"🎬 {s['title']}", callback_data=f"browse_sec_{s['id']}_0_{skip}")
            ])
            
    pag_row = []
    if skip > 0:
        pag_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"manage_series_skip_{max(0, skip - limit)}"))
    if skip + limit < len(series_list):
        pag_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"manage_series_skip_{skip + limit}"))
    if pag_row:
        buttons.append(pag_row)
    
    buttons.append([
        InlineKeyboardButton("⚙️ Series Management", callback_data="series_management_menu")
    ])
    buttons.append(get_back_button("manage_files"))
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        print(f"Error rendering manage_series: {e}")

async def show_series_management_menu(client: Client, chat_id: int, message_id: int):
    settings = await database.get_settings()
    limit = settings.get("series_buttons_per_page", 5)
    custom_msg = settings.get("series_library_custom_msg")
    msg_status = "Set ✅" if custom_msg else "Not Set ❌"
    
    text = (
        "⚙️ **Series Library Management**\n\n"
        f"🔢 **User Series Pagination Limit:** `{limit}` buttons per page\n"
        f"💬 **Library Custom Message:** {msg_status}\n\n"
        "Choose a configuration option below:"
    )
    
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔢 Edit Buttons per Page", callback_data="edit_series_pag_limit"),
            InlineKeyboardButton("💬 Edit Library Message", callback_data="edit_series_library_msg")
        ],
        [
            InlineKeyboardButton("↕️ Reorder Series List", callback_data="series_reorder_menu")
        ],
        [
            InlineKeyboardButton("🔙 Back to Series Library", callback_data="manage_series")
        ]
    ])
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    except Exception as e:
        print(f"Error rendering series_management_menu: {e}")

async def show_series_reorder_menu(client: Client, chat_id: int, message_id: int, selected_ids: list = None):
    if selected_ids is None:
        selected_ids = []
        
    def get_number_emoji(num: int) -> str:
        emojis = {
            1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣",
            6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣", 10: "🔟"
        }
        return emojis.get(num, f"[{num}]")
        
    series_list = await database.list_series()
    text = (
        "↕️ **Reorder Video Series**\n\n"
        "Select the series in the order you want them to display. "
        "Selected ones will show first (in selection sequence), and remaining unselected series will follow in their current relative order:\n\n"
    )
    
    if selected_ids:
        text += "📝 **Current Selection Order:**\n"
        for idx, sid in enumerate(selected_ids):
            for s in series_list:
                if s["id"] == sid:
                    text += f"{get_number_emoji(idx + 1)} {s['title']}\n"
                    break
        text += "\n"
        
    buttons = []
    
    for s in series_list:
        sid = s["id"]
        is_selected = sid in selected_ids
        
        display_title = s["title"]
        if is_selected:
            idx = selected_ids.index(sid)
            checkbox_text = get_number_emoji(idx + 1)
        else:
            checkbox_text = "⬜"
            
        row = [
            InlineKeyboardButton(f"🎬 {display_title}", callback_data="noop"),
            InlineKeyboardButton(checkbox_text, callback_data=f"reorder_toggle_{sid}")
        ]
        buttons.append(row)
        
    if len(selected_ids) >= 2:
        buttons.append([
            InlineKeyboardButton(f"✅ Confirm Reorder ({len(selected_ids)} selected)", callback_data="reorder_confirm")
        ])
        
    buttons.append([InlineKeyboardButton("🔙 Back to Series Management", callback_data="series_management_menu")])
    
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        print(f"Error rendering show_series_reorder_menu: {e}")

async def show_manage_files(client: Client, chat_id: int, message_id: int):
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📤 Store New File", callback_data="add_file"),
            InlineKeyboardButton("➕ Create Series", callback_data="create_series")
        ],
        [
            InlineKeyboardButton("🎬 Series Library", callback_data="manage_series")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="main_panel")
        ]
    ])
    try:
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="📂 **File and Series Management**\n\nHere you can add new media files, view stored files, and create/manage video/episodes series.",
            reply_markup=markup
        )
    except Exception as e:
        print(f"Error rendering manage_files: {e}")

async def show_filesec_actions(client: Client, chat_id: int, message_id: int, series_id: int, section_id: int, sec: dict, total_files: int, library_skip: int = 0):
    parent_id = sec["parent_id"]
    text = f"📥 **{sec['name']}**\n\n📂 Contains **{total_files} file(s)**\n\nChoose an action:"
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add More Files", callback_data=f"filesec_add_{series_id}_{section_id}"),
            InlineKeyboardButton("🔄 Replace All Files", callback_data=f"filesec_replace_{series_id}_{section_id}")
        ],
        [
            InlineKeyboardButton("✏️ Rename Button", callback_data=f"rename_sec_{series_id}_{section_id}"),
            InlineKeyboardButton("🗑 Delete Button", callback_data=f"tree_del_sec_{series_id}_{section_id}")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"browse_sec_{series_id}_{parent_id or 0}_{library_skip}")
        ]
    ])
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    except Exception as e:
        print(f"Error rendering filesec_actions: {e}")

async def show_move_folder_menu(client: Client, chat_id: int, message_id: int, series_id: int, section_id: int, skip: int = 0, library_skip: int = 0):
    series = await database.get_series(series_id)
    folder_to_move = await database.get_section(section_id)
    if not series or not folder_to_move:
        try:
            await client.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ Folder or Series not found.")
        except Exception:
            pass
        return

    # Fetch all folders in this series
    all_folders = await database.list_all_folders(series_id)
    
    # Exclude itself and any descendants to prevent loops
    descendants = set()
    
    def add_descendants(parent_id):
        for f in all_folders:
            if f["parent_id"] == parent_id:
                if f["id"] not in descendants:
                    descendants.add(f["id"])
                    add_descendants(f["id"])
                    
    descendants.add(section_id)
    add_descendants(section_id)
    
    # Filter valid target folders
    valid_folders = [f for f in all_folders if f["id"] not in descendants]
    
    text = (
        f"📂 **Move Folder: {folder_to_move['name']}**\n\n"
        f"Choose a new parent folder for **{folder_to_move['name']}** from the list below.\n"
        "Select **Root (Top-Level)** to move it to the series root."
    )
    
    buttons = []
    
    # Always allow moving to Root (Top-Level) if currently not at root
    if folder_to_move["parent_id"] is not None:
        buttons.append([
            InlineKeyboardButton("📁 Root (Top-Level)", callback_data=f"move_folder_execute_{series_id}_{section_id}_root_{library_skip}")
        ])
        
    # Page valid folders
    limit = 5
    page_folders = valid_folders[skip:skip+limit]
    
    for f in page_folders:
        prefix = "👉 " if f["id"] == folder_to_move["parent_id"] else "📁 "
        buttons.append([
            InlineKeyboardButton(f"{prefix}{f['name']}", callback_data=f"move_folder_execute_{series_id}_{section_id}_{f['id']}_{library_skip}")
        ])
        
    # Pagination
    pag_row = []
    if skip > 0:
        pag_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"move_folder_select_{series_id}_{section_id}_{library_skip}_{max(0, skip - limit)}"))
    if skip + limit < len(valid_folders):
        pag_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"move_folder_select_{series_id}_{section_id}_{library_skip}_{skip + limit}"))
    if pag_row:
        buttons.append(pag_row)
        
    buttons.append([
        InlineKeyboardButton("🔙 Cancel / Back", callback_data=f"manage_folder_opt_{series_id}_{section_id}_{library_skip}")
    ])
    
    try:
        await client.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        print(f"Error rendering show_move_folder_menu: {e}")

