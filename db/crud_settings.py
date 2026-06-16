import time
import asyncio
import psycopg2
from .models import SessionLocal, Settings, CloneBot, User, Admin, Subscriber, RemotePremiumCache
from datetime import datetime
from config import SUBSCRIPTION_DATABASE_URL



def _get_settings_sync():
    global _SETTINGS_CACHE, _SETTINGS_CACHE_EXPIRY
    if _SETTINGS_CACHE and time.time() < _SETTINGS_CACHE_EXPIRY:
        return _SETTINGS_CACHE
    with SessionLocal() as session:
        settings = session.query(Settings).first()
        if not settings:
            settings = Settings(id=1)
            session.add(settings)
            session.commit()
            session.refresh(settings)
        result = {
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
            "access_to_all": settings.access_to_all,
            "lock_buttons_enabled": settings.lock_buttons_enabled,
            "protect_content_enabled": settings.protect_content_enabled,
            "lock_time_window": settings.lock_time_window,
            "testing_mode": settings.testing_mode
        }
    _SETTINGS_CACHE = result
    _SETTINGS_CACHE_EXPIRY = time.time() + SETTINGS_CACHE_TTL
    return result

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
    clear_settings_cache()

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


# --- Premium & Sync Management with Memory Caching ---

# In-memory premium check cache to make clone bot page transitions/checks extremely fast
# Keys: user_id (int)
# Values: (is_premium: bool, expiry_time: float)
USER_PREMIUM_MEMORY_CACHE = {}
# TTL in seconds — 5 minutes is fresh enough for most use cases
USER_PREMIUM_CACHE_TTL = 300

# In-memory settings cache to avoid repeated local DB reads on every navigation click
_SETTINGS_CACHE = {}
_SETTINGS_CACHE_EXPIRY = 0.0
SETTINGS_CACHE_TTL = 120  # 2 minutes

def clear_user_premium_mem_cache(user_id: int = None):
    global USER_PREMIUM_MEMORY_CACHE
    if user_id:
        USER_PREMIUM_MEMORY_CACHE.pop(user_id, None)
    else:
        USER_PREMIUM_MEMORY_CACHE.clear()

def clear_settings_cache():
    global _SETTINGS_CACHE, _SETTINGS_CACHE_EXPIRY
    _SETTINGS_CACHE = {}
    _SETTINGS_CACHE_EXPIRY = 0.0

def _is_premium_user_sync(user_id: int, owner_id: int) -> bool:
    # 1. Bot owner is always premium
    if user_id == owner_id:
        return True

    # 2. Check in-memory cache first (fast path — avoids ALL DB calls on repeated navigation)
    cached = USER_PREMIUM_MEMORY_CACHE.get(user_id)
    if cached is not None:
        is_premium, expiry = cached
        if time.time() < expiry:
            return is_premium
        # Expired — remove from cache
        USER_PREMIUM_MEMORY_CACHE.pop(user_id, None)

    # 3. Check if admin
    with SessionLocal() as session:
        admin = session.query(Admin).filter(Admin.user_id == user_id).first()
        if admin:
            USER_PREMIUM_MEMORY_CACHE[user_id] = (True, time.time() + USER_PREMIUM_CACHE_TTL)
            return True

        # 4. Check if local subscriber (manual premium subscriber)
        sub = session.query(Subscriber).filter(Subscriber.user_id == user_id).first()
        if sub:
            USER_PREMIUM_MEMORY_CACHE[user_id] = (True, time.time() + USER_PREMIUM_CACHE_TTL)
            return True

    # 5. Check local remote_premium_cache table (fast local DB lookup)
    with SessionLocal() as session:
        settings = session.query(Settings).first()
        if settings and settings.testing_mode:
            USER_PREMIUM_MEMORY_CACHE[user_id] = (False, time.time() + USER_PREMIUM_CACHE_TTL)
            return False

        cache_rec = session.query(RemotePremiumCache).filter(RemotePremiumCache.user_id == user_id).first()
        if cache_rec and cache_rec.expiry_date:
            try:
                expiry = datetime.strptime(cache_rec.expiry_date, "%d/%m/%Y").replace(hour=23, minute=59, second=59)
                if expiry >= datetime.now():
                    USER_PREMIUM_MEMORY_CACHE[user_id] = (True, time.time() + USER_PREMIUM_CACHE_TTL)
                    return True
            except Exception:
                pass

    # 6. If not cached, treat as normal user
    USER_PREMIUM_MEMORY_CACHE[user_id] = (False, time.time() + USER_PREMIUM_CACHE_TTL)
    return False



def _sync_premium_users_sync() -> int:
    """
    Connects to the remote Subscriptionbot database, fetches all active plan 1/3 subscriptions,
    and bulk-replaces the local remote_premium_cache table.
    Returns the count of synced active subscriptions.
    """
    if not SUBSCRIPTION_DATABASE_URL:
        print("Error: SUBSCRIPTION_DATABASE_URL not configured.")
        return 0

    conn = None
    try:
        conn = psycopg2.connect(SUBSCRIPTION_DATABASE_URL, sslmode='require')
        with conn.cursor() as cursor:
            # Query active subscriptions for plan ID 1
            cursor.execute("""
                SELECT user_id, plan_id, plan_name, expiry_date, status
                FROM subscriptions
                WHERE plan_id = 1 AND status IN ('Paid', 'Granted') AND expiry_date IS NOT NULL
            """)
            rows = cursor.fetchall()
            
            # Write to local cache
            with SessionLocal() as session:
                # 1. Clear existing cache
                session.query(RemotePremiumCache).delete()
                
                # 2. Bulk insert active ones
                count = 0
                for r in rows:
                    uid, plan_id, plan_name, expiry_str, status = r
                    # Validate expiry date is not already passed
                    try:
                        expiry = datetime.strptime(expiry_str, "%d/%m/%Y").replace(hour=23, minute=59, second=59)
                        if expiry >= datetime.now():
                            cache_rec = RemotePremiumCache(
                                user_id=uid,
                                plan_id=plan_id,
                                plan_name=plan_name,
                                expiry_date=expiry_str,
                                last_checked=datetime.utcnow()
                            )
                            session.add(cache_rec)
                            count += 1
                    except Exception:
                        pass
                session.commit()
                # Clear all user in-memory cache to force refresh
                clear_user_premium_mem_cache()
                return count
    except Exception as e:
        print(f"Error during remote sync: {e}")
        return 0
    finally:
        if conn:
            conn.close()


def _sync_single_premium_user_sync(user_id: int) -> bool:
    """
    Connects to the remote Subscriptionbot database, queries the active subscription for a specific user,
    and updates the local cache table.
    Returns True if user has an active premium subscription, False otherwise.
    """
    if not SUBSCRIPTION_DATABASE_URL:
        return False

    conn = None
    try:
        conn = psycopg2.connect(SUBSCRIPTION_DATABASE_URL, sslmode='require')
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT user_id, plan_id, plan_name, expiry_date, status
                FROM subscriptions
                WHERE user_id = %s AND plan_id = 1 AND status IN ('Paid', 'Granted') AND expiry_date IS NOT NULL
                ORDER BY sub_id DESC LIMIT 1
            """, (user_id,))
            r = cursor.fetchone()
            
            with SessionLocal() as session:
                if r:
                    uid, plan_id, plan_name, expiry_str, status = r
                    try:
                        expiry = datetime.strptime(expiry_str, "%d/%m/%Y").replace(hour=23, minute=59, second=59)
                        if expiry >= datetime.now():
                            # Update or insert
                            cache_rec = session.query(RemotePremiumCache).filter(RemotePremiumCache.user_id == user_id).first()
                            if not cache_rec:
                                cache_rec = RemotePremiumCache(user_id=user_id)
                                session.add(cache_rec)
                            cache_rec.plan_id = plan_id
                            cache_rec.plan_name = plan_name
                            cache_rec.expiry_date = expiry_str
                            cache_rec.last_checked = datetime.utcnow()
                            session.commit()
                            clear_user_premium_mem_cache(user_id)
                            return True
                    except Exception:
                        pass
                
                # If no active subscription returned or it is expired, delete local cache if any
                cache_rec = session.query(RemotePremiumCache).filter(RemotePremiumCache.user_id == user_id).first()
                if cache_rec:
                    session.delete(cache_rec)
                    session.commit()
                clear_user_premium_mem_cache(user_id)
                return False
    except Exception as e:
        print(f"Error syncing single user {user_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def _get_premium_cache_count_sync() -> int:
    with SessionLocal() as session:
        # Check active cached users (unexpired)
        count = 0
        caches = session.query(RemotePremiumCache).all()
        for c in caches:
            if c.expiry_date:
                try:
                    expiry = datetime.strptime(c.expiry_date, "%d/%m/%Y").replace(hour=23, minute=59, second=59)
                    if expiry >= datetime.now():
                        count += 1
                except Exception:
                    pass
        return count


# --- Async wrappers ---
async def is_premium_user(user_id: int, owner_id: int) -> bool:
    return await asyncio.to_thread(_is_premium_user_sync, user_id, owner_id)

async def sync_premium_users() -> int:
    return await asyncio.to_thread(_sync_premium_users_sync)

async def sync_single_premium_user(user_id: int) -> bool:
    return await asyncio.to_thread(_sync_single_premium_user_sync, user_id)

async def get_premium_cache_count() -> int:
    return await asyncio.to_thread(_get_premium_cache_count_sync)


def _get_remote_channels_sync():
    if not SUBSCRIPTION_DATABASE_URL:
        return []
    conn = None
    try:
        conn = psycopg2.connect(SUBSCRIPTION_DATABASE_URL, sslmode='require')
        with conn.cursor() as cursor:
            cursor.execute("SELECT title, invite_link FROM premium_channels WHERE invite_link IS NOT NULL AND invite_link != ''")
            rows = cursor.fetchall()
            return [{"title": r[0], "invite_link": r[1]} for r in rows]
    except Exception as e:
        print(f"Error fetching remote channels: {e}")
        return []
    finally:
        if conn:
            conn.close()

async def get_remote_channels():
    return await asyncio.to_thread(_get_remote_channels_sync)


