import asyncio
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Text, Boolean, DateTime, ForeignKey, text
from sqlalchemy.orm import declarative_base, sessionmaker
from config import DATABASE_URL

# Create database engine and session
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
Base = declarative_base()

# Models
class Settings(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, default=1)
    welcome_msg = Column(Text, default="Hey {mention}, welcome to {bot_name}!")
    fsub_channels = Column(Text, default="")
    fsub_enabled = Column(Boolean, default=False)
    custom_buttons = Column(Text, default="[]")  # JSON string of list of dicts
    primary_clone_username = Column(String, default="")
    db_channel_id = Column(String, default="")
    log_channel_id = Column(String, default="")
    auto_delete_enabled = Column(Boolean, default=False)
    auto_delete_duration = Column(Integer, default=5)
    series_buttons_per_page = Column(Integer, default=5)
    start_end_msg_enabled = Column(Boolean, default=False)
    start_msg_db_id = Column(Integer, nullable=True)
    end_msg_db_id = Column(Integer, nullable=True)
    series_library_custom_msg = Column(Text, default=None)
    user_send_delay = Column(Integer, default=3)
    db_upload_delay = Column(Integer, default=3)
    access_to_all = Column(Boolean, default=True)

class CloneBot(Base):
    __tablename__ = "clone_bots"
    token = Column(String, primary_key=True)
    username = Column(String, nullable=False)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=False)

class Series(Base):
    __tablename__ = "series"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    custom_msg = Column(Text, nullable=True)
    buttons_per_row = Column(Integer, default=2)
    display_order = Column(Integer, default=0)

class SeriesSection(Base):
    __tablename__ = "series_sections"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    series_id = Column(Integer, ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("series_sections.id", ondelete="CASCADE"), nullable=True)
    sec_type = Column(String, server_default="folder", default="folder")
    custom_msg = Column(Text, nullable=True)
    buttons_per_row = Column(Integer, default=2)

class FileRecord(Base):
    __tablename__ = "files"
    file_code = Column(String, primary_key=True)
    message_id = Column(Integer, nullable=False)
    file_name = Column(String, default="")
    file_size = Column(BigInteger, default=0)
    mime_type = Column(String, default="")
    caption = Column(Text, default="")
    series_id = Column(Integer, ForeignKey("series.id", ondelete="SET NULL"), nullable=True)
    episode_number = Column(Integer, nullable=True)
    section_id = Column(Integer, ForeignKey("series_sections.id", ondelete="CASCADE"), nullable=True)

class User(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow)

class Admin(Base):
    __tablename__ = "admins"
    user_id = Column(BigInteger, primary_key=True)

class Subscriber(Base):
    __tablename__ = "subscribers"
    user_id = Column(BigInteger, primary_key=True)
    first_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow)

# Helper to initialize DB
def db_init():
    Base.metadata.create_all(engine)
    from sqlalchemy import inspect
    inspector = inspect(engine)
    
    # files columns check
    columns = [c["name"] for c in inspector.get_columns("files")]
    if "section_id" not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE files ADD COLUMN section_id INTEGER REFERENCES series_sections(id) ON DELETE CASCADE"))
            conn.commit()
            
    # series_sections columns check
    columns_sec = [c["name"] for c in inspector.get_columns("series_sections")]
    if "sec_type" not in columns_sec:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE series_sections ADD COLUMN sec_type VARCHAR DEFAULT 'folder'"))
            conn.commit()
    if "custom_msg" not in columns_sec:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE series_sections ADD COLUMN custom_msg TEXT DEFAULT NULL"))
            conn.commit()
    if "buttons_per_row" not in columns_sec:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE series_sections ADD COLUMN buttons_per_row INTEGER DEFAULT 2"))
            conn.commit()

    # settings columns check
    columns_sett = [c["name"] for c in inspector.get_columns("settings")]
    if "auto_delete_enabled" not in columns_sett:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE settings ADD COLUMN auto_delete_enabled BOOLEAN DEFAULT FALSE"))
            conn.commit()
    if "auto_delete_duration" not in columns_sett:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE settings ADD COLUMN auto_delete_duration INTEGER DEFAULT 5"))
            conn.commit()
    if "series_buttons_per_page" not in columns_sett:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE settings ADD COLUMN series_buttons_per_page INTEGER DEFAULT 5"))
            conn.commit()
    if "start_end_msg_enabled" not in columns_sett:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE settings ADD COLUMN start_end_msg_enabled BOOLEAN DEFAULT FALSE"))
            conn.commit()
    if "start_msg_db_id" not in columns_sett:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE settings ADD COLUMN start_msg_db_id INTEGER DEFAULT NULL"))
            conn.commit()
    if "end_msg_db_id" not in columns_sett:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE settings ADD COLUMN end_msg_db_id INTEGER DEFAULT NULL"))
            conn.commit()
    if "series_library_custom_msg" not in columns_sett:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE settings ADD COLUMN series_library_custom_msg TEXT DEFAULT NULL"))
            conn.commit()
    if "user_send_delay" not in columns_sett:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE settings ADD COLUMN user_send_delay INTEGER DEFAULT 3"))
            conn.commit()
    if "db_upload_delay" not in columns_sett:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE settings ADD COLUMN db_upload_delay INTEGER DEFAULT 3"))
            conn.commit()
    if "access_to_all" not in columns_sett:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE settings ADD COLUMN access_to_all BOOLEAN DEFAULT TRUE"))
            conn.commit()

    # series columns check
    columns_ser = [c["name"] for c in inspector.get_columns("series")]
    if "custom_msg" not in columns_ser:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE series ADD COLUMN custom_msg TEXT DEFAULT NULL"))
            conn.commit()
    if "buttons_per_row" not in columns_ser:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE series ADD COLUMN buttons_per_row INTEGER DEFAULT 2"))
            conn.commit()
    if "display_order" not in columns_ser:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE series ADD COLUMN display_order INTEGER DEFAULT 0"))
            conn.commit()

    # Auto-migrate: any section that owns file records must be sec_type='files'
    with engine.connect() as conn:
        conn.execute(text(
            "UPDATE series_sections SET sec_type = 'files' "
            "WHERE id IN (SELECT DISTINCT section_id FROM files WHERE section_id IS NOT NULL) "
            "AND (sec_type IS NULL OR sec_type != 'files')"
        ))
        conn.commit()

    # Ensure settings row exists
    with SessionLocal() as session:
        settings = session.query(Settings).first()
        if not settings:
            settings = Settings(id=1)
            session.add(settings)
            session.commit()
