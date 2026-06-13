import asyncio
from .models import SessionLocal, Settings, CloneBot, User, Admin, Subscriber
from datetime import datetime

def _get_settings_sync():
    with SessionLocal() as session:
        settings = session.query(Settings).first()
        if not settings:
            settings = Settings(id=1)
            session.add(settings)
            session.commit()
            session.refresh(settings)
        return {
            "welcome_msg": settings.welcome_msg,
            "fsub_channels": settings.fsub_channels,
            "fsub_enabled": settings.fsub_enabled,
            "custom_buttons": settings.custom_buttons,
            "primary_clone_username": settings.primary_clone_username,
            "db_channel_id": settings.db_channel_id,
            "log_channel_id": settings.log_channel_id,
            "auto_delete_enabled": settings.auto_delete_enabled,
            "auto_delete_duration": settings.auto_delete_duration,
            "series_buttons_per_page": settings.series_buttons_per_page,
            "start_end_msg_enabled": settings.start_end_msg_enabled,
            "start_msg_db_id": settings.start_msg_db_id,
            "end_msg_db_id": settings.end_msg_db_id,
            "series_library_custom_msg": settings.series_library_custom_msg,
            "user_send_delay": settings.user_send_delay,
            "db_upload_delay": settings.db_upload_delay,
            "access_to_all": settings.access_to_all
        }

def _update_settings_sync(updates: dict):
    with SessionLocal() as session:
        settings = session.query(Settings).first()
        if not settings:
            settings = Settings(id=1)
            session.add(settings)
        for key, value in updates.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        session.commit()

def _add_clone_bot_sync(token: str, username: str, name: str):
    with SessionLocal() as session:
        bot = session.query(CloneBot).filter(CloneBot.token == token).first()
        if not bot:
            bot = CloneBot(token=token, username=username, name=name, is_active=False)
            session.add(bot)
        else:
            bot.username = username
            bot.name = name
        session.commit()

def _get_clone_bots_sync():
    with SessionLocal() as session:
        bots = session.query(CloneBot).all()
        return [{"token": b.token, "username": b.username, "name": b.name, "is_active": b.is_active} for b in bots]

def _set_clone_bot_status_sync(token: str, is_active: bool):
    with SessionLocal() as session:
        bot = session.query(CloneBot).filter(CloneBot.token == token).first()
        if bot:
            bot.is_active = is_active
            session.commit()

def _delete_clone_bot_sync(token: str):
    with SessionLocal() as session:
        bot = session.query(CloneBot).filter(CloneBot.token == token).first()
        if bot:
            session.delete(bot)
            session.commit()

def _add_user_sync(user_id: int, username: str, first_name: str) -> bool:
    with SessionLocal() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            user = User(user_id=user_id, username=username, first_name=first_name)
            session.add(user)
            session.commit()
            return True
        return False

def _get_user_count_sync():
    with SessionLocal() as session:
        return session.query(User).count()

def _list_users_sync(limit=100):
    with SessionLocal() as session:
        users = session.query(User).order_by(User.joined_at.desc()).limit(limit).all()
        return [{"user_id": u.user_id, "username": u.username, "first_name": u.first_name, "joined_at": u.joined_at.isoformat()} for u in users]

def _is_admin_sync(user_id: int, owner_id: int):
    if user_id == owner_id:
        return True
    with SessionLocal() as session:
        admin = session.query(Admin).filter(Admin.user_id == user_id).first()
        return admin is not None

def _add_admin_sync(user_id: int):
    with SessionLocal() as session:
        admin = session.query(Admin).filter(Admin.user_id == user_id).first()
        if not admin:
            admin = Admin(user_id=user_id)
            session.add(admin)
            session.commit()

def _remove_admin_sync(user_id: int):
    with SessionLocal() as session:
        admin = session.query(Admin).filter(Admin.user_id == user_id).first()
        if admin:
            session.delete(admin)
            session.commit()

# --- Async wrappers ---
async def get_settings():
    return await asyncio.to_thread(_get_settings_sync)

async def update_settings(updates: dict):
    await asyncio.to_thread(_update_settings_sync, updates)

async def add_clone_bot(token: str, username: str, name: str):
    await asyncio.to_thread(_add_clone_bot_sync, token, username, name)

async def get_clone_bots():
    return await asyncio.to_thread(_get_clone_bots_sync)

async def set_clone_bot_status(token: str, is_active: bool):
    await asyncio.to_thread(_set_clone_bot_status_sync, token, is_active)

async def delete_clone_bot(token: str):
    await asyncio.to_thread(_delete_clone_bot_sync, token)

async def add_user(user_id: int, username: str, first_name: str) -> bool:
    return await asyncio.to_thread(_add_user_sync, user_id, username, first_name)

async def get_user_count():
    return await asyncio.to_thread(_get_user_count_sync)

async def list_users(limit=100):
    return await asyncio.to_thread(_list_users_sync, limit)

async def is_admin(user_id: int, owner_id: int):
    return await asyncio.to_thread(_is_admin_sync, user_id, owner_id)

async def add_admin(user_id: int):
    await asyncio.to_thread(_add_admin_sync, user_id)

async def remove_admin(user_id: int):
    await asyncio.to_thread(_remove_admin_sync, user_id)

# --- Subscriber Sync Functions ---
def _add_subscriber_sync(user_id: int, first_name: str = None, username: str = None) -> bool:
    with SessionLocal() as session:
        sub = session.query(Subscriber).filter(Subscriber.user_id == user_id).first()
        if not sub:
            if not first_name:
                user = session.query(User).filter(User.user_id == user_id).first()
                if user:
                    first_name = user.first_name
                    username = user.username
            
            sub = Subscriber(
                user_id=user_id,
                first_name=first_name or f"User {user_id}",
                username=username
            )
            session.add(sub)
            session.commit()
            return True
        return False

def _remove_subscriber_sync(user_id: int) -> bool:
    with SessionLocal() as session:
        sub = session.query(Subscriber).filter(Subscriber.user_id == user_id).first()
        if sub:
            session.delete(sub)
            session.commit()
            return True
        return False

def _is_subscriber_sync(user_id: int) -> bool:
    with SessionLocal() as session:
        sub = session.query(Subscriber).filter(Subscriber.user_id == user_id).first()
        return sub is not None

def _get_subscriber_count_sync() -> int:
    with SessionLocal() as session:
        return session.query(Subscriber).count()

def _list_subscribers_sync(skip: int = 0, limit: int = 5):
    with SessionLocal() as session:
        total = session.query(Subscriber).count()
        subs = session.query(Subscriber).order_by(Subscriber.joined_at.desc()).offset(skip).limit(limit).all()
        subs_list = [{
            "user_id": s.user_id,
            "first_name": s.first_name,
            "username": s.username,
            "joined_at": s.joined_at.isoformat()
        } for s in subs]
        return subs_list, total

# --- Subscriber Async Wrappers ---
async def add_subscriber(user_id: int, first_name: str = None, username: str = None) -> bool:
    return await asyncio.to_thread(_add_subscriber_sync, user_id, first_name, username)

async def remove_subscriber(user_id: int) -> bool:
    return await asyncio.to_thread(_remove_subscriber_sync, user_id)

async def is_subscriber(user_id: int) -> bool:
    return await asyncio.to_thread(_is_subscriber_sync, user_id)

async def get_subscriber_count() -> int:
    return await asyncio.to_thread(_get_subscriber_count_sync)

async def list_subscribers(skip: int = 0, limit: int = 5):
    return await asyncio.to_thread(_list_subscribers_sync, skip, limit)
