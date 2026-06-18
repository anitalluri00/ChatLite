from __future__ import annotations

import base64
import binascii
from collections import Counter
from difflib import SequenceMatcher
from email.message import EmailMessage
import hashlib
import hmac
import importlib
import inspect
import io
import json
import os
import random
import re
import smtplib
import sqlite3
import ssl
import uuid
import zlib
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import streamlit as st

try:
    import streamlit.components.v1 as components
except ImportError:
    components = None

try:
    FILE_UPLOADER_SUPPORTS_MAX_UPLOAD_SIZE = "max_upload_size" in inspect.signature(st.file_uploader).parameters
except (TypeError, ValueError):
    FILE_UPLOADER_SUPPORTS_MAX_UPLOAD_SIZE = False

try:
    import phonenumbers
except ImportError:
    phonenumbers = None

try:
    import pycountry
except ImportError:
    pycountry = None

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding as asymmetric_padding
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    Fernet = None
    InvalidToken = Exception
    hashes = None
    serialization = None
    asymmetric_padding = None
    rsa = None

try:
    import psycopg
    from psycopg.types.json import Jsonb
except ImportError:
    psycopg = None
    Jsonb = None


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


APP_TITLE = "ChatLite"
APP_SECRET = os.getenv("CHATLITE_APP_SECRET", "chatlite-local-development-secret")
DATABASE_URL = os.getenv("CHATLITE_DATABASE_URL") or os.getenv("DATABASE_URL", "")
SMTP_HOST = os.getenv("CHATLITE_SMTP_HOST", "")
SMTP_PORT = max(1, env_int("CHATLITE_SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("CHATLITE_SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("CHATLITE_SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("CHATLITE_SMTP_FROM_EMAIL", SMTP_USERNAME or "no-reply@chatlite.local")
PUSH_WEBHOOK_URL = os.getenv("CHATLITE_PUSH_WEBHOOK_URL", "")
ONESIGNAL_APP_ID = os.getenv("CHATLITE_ONESIGNAL_APP_ID", "")
ONESIGNAL_API_KEY = os.getenv("CHATLITE_ONESIGNAL_API_KEY", "")
FIREBASE_CREDENTIALS_FILE = os.getenv("CHATLITE_FIREBASE_CREDENTIALS_FILE", "")
FIREBASE_TOPIC = os.getenv("CHATLITE_FIREBASE_TOPIC", "chatlite")
REALTIME_WS_URL = os.getenv("CHATLITE_REALTIME_WS_URL", "").rstrip("/")
OBJECT_STORAGE_PROVIDER = os.getenv("CHATLITE_OBJECT_STORAGE_PROVIDER", "local").strip().lower()
OBJECT_STORAGE_BUCKET = os.getenv("CHATLITE_OBJECT_STORAGE_BUCKET", "")
OBJECT_STORAGE_ENDPOINT = os.getenv("CHATLITE_OBJECT_STORAGE_ENDPOINT", "")
OBJECT_STORAGE_ACCESS_KEY = os.getenv("CHATLITE_OBJECT_STORAGE_ACCESS_KEY", "")
OBJECT_STORAGE_SECRET_KEY = os.getenv("CHATLITE_OBJECT_STORAGE_SECRET_KEY", "")
SQLITE_FILE = Path(os.getenv("CHATLITE_SQLITE_FILE", "chatlite_data.sqlite3")).expanduser()
LEGACY_DATA_FILE = Path(os.getenv("CHATLITE_DATA_FILE", "chatlite_data.json")).expanduser()
STORAGE_BACKEND = os.getenv("CHATLITE_STORAGE_BACKEND", "").strip().lower()
USERNAME_PATTERN = re.compile(r"^[a-z0-9_]{3,20}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^[0-9][0-9 .()/-]{4,24}$")
ACCENTS = ["#04986d", "#2f80ed", "#f59e0b", "#7c3aed", "#e11d48", "#0f766e"]
THEMES = ["Light", "Dark"]
GROUP_PREFIX = "group::"
MAX_ATTACHMENT_BYTES = max(1, env_int("CHATLITE_MAX_ATTACHMENT_BYTES", 3_000_000))
TYPING_DEBOUNCE_SECONDS = max(1, env_int("CHATLITE_TYPING_DEBOUNCE_SECONDS", 3))
BACKUP_RETENTION_LIMIT = max(1, env_int("CHATLITE_BACKUP_RETENTION", 8))
RATE_LIMIT_RULES = {
    "message": (30, 60),
    "login": (6, 15 * 60),
    "password_reset": (3, 60 * 60),
    "friend_request": (10, 60 * 60),
}
IMPORTANT_KEYWORDS = {
    "urgent",
    "important",
    "asap",
    "deadline",
    "meeting",
    "help",
    "blocked",
    "issue",
}
SUMMARY_STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "because",
    "before",
    "being",
    "chat",
    "could",
    "from",
    "have",
    "into",
    "just",
    "like",
    "message",
    "that",
    "their",
    "there",
    "this",
    "with",
    "will",
    "your",
}
DEFAULT_BLOCKED_WORDS = {
    word.strip().lower()
    for word in os.getenv("CHATLITE_BLOCKED_WORDS", "abuse,scam,fraud,phishing,hate,kill,terror").split(",")
    if word.strip()
}
URL_PATTERN = re.compile(r"https?://[^\s<]+|www\.[^\s<]+", re.IGNORECASE)
SHORT_LINK_PATTERN = re.compile(r"\b(bit\.ly|tinyurl\.com|t\.co|goo\.gl|ow\.ly|is\.gd)\b", re.IGNORECASE)
WORD_PATTERN = re.compile(r"[a-z0-9']+")
MESSAGE_TEXT_FAILURES = {
    "Compressed message could not be decoded",
    "Encrypted message unavailable",
    "Encrypted message could not be decrypted",
}
MEDIA_EXTENSIONS = [
    "jpg",
    "jpeg",
    "png",
    "webp",
    "gif",
    "pdf",
    "txt",
    "csv",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "mp3",
    "wav",
    "m4a",
    "mp4",
    "mov",
    "webm",
]
REACTION_OPTIONS = ["like", "love", "laugh", "wow", "sad", "thanks"]
DISAPPEARING_OPTIONS = {
    "Off": 0,
    "1 hour": 60 * 60,
    "24 hours": 24 * 60 * 60,
    "7 days": 7 * 24 * 60 * 60,
}
CALL_TYPES = ["voice", "video"]
TOPIC_KEYWORDS = {
    "work": {"deadline", "meeting", "project", "ticket", "deploy", "review", "client"},
    "family": {"family", "home", "mom", "dad", "birthday", "dinner"},
    "urgent": {"urgent", "asap", "blocked", "critical", "issue", "help"},
    "finance": {"invoice", "payment", "budget", "cost", "billing"},
    "travel": {"flight", "hotel", "trip", "booking", "train"},
}
PHOTO_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
FALLBACK_COUNTRY_CODES = [
    {"label": "United States (+1)", "code": "+1", "region": "US"},
    {"label": "India (+91)", "code": "+91", "region": "IN"},
    {"label": "United Kingdom (+44)", "code": "+44", "region": "GB"},
    {"label": "Canada (+1)", "code": "+1", "region": "CA"},
    {"label": "Australia (+61)", "code": "+61", "region": "AU"},
    {"label": "Germany (+49)", "code": "+49", "region": "DE"},
    {"label": "France (+33)", "code": "+33", "region": "FR"},
    {"label": "Japan (+81)", "code": "+81", "region": "JP"},
    {"label": "Singapore (+65)", "code": "+65", "region": "SG"},
    {"label": "United Arab Emirates (+971)", "code": "+971", "region": "AE"},
]
SEED_EMAILS = {
    "demo": "demo@chatlite.local",
    "aisha": "aisha@chatlite.local",
    "michael": "michael@chatlite.local",
    "nina": "nina@chatlite.local",
}


def normalize_username(value: str) -> str:
    return value.strip().lower()


def normalize_email(value: str) -> str:
    return value.strip().lower()


def is_valid_username(username: str) -> bool:
    return bool(USERNAME_PATTERN.fullmatch(username))


def password_hash(username: str, password: str) -> str:
    salt = f"chatlite:{username}".encode("utf-8")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return digest.hex()


def verify_password(username: str, password: str, stored_hash: str) -> bool:
    return hmac.compare_digest(password_hash(username, password), stored_hash)


def current_time() -> str:
    return datetime.now().strftime("%H:%M")


def current_stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_stamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def timestamp_sort_value(value: str | None) -> float:
    parsed = parse_stamp(value)
    return parsed.timestamp() if parsed else 0.0


def upload_limit_mb() -> int:
    return max(1, (MAX_ATTACHMENT_BYTES + 999_999) // 1_000_000)


def file_uploader_compat(
    label: str,
    *,
    file_types: list[str],
    accept_multiple_files: bool,
    key: str,
    max_upload_size: int | None = None,
    disabled: bool = False,
) -> Any:
    kwargs: dict[str, Any] = {
        "label": label,
        "type": file_types,
        "accept_multiple_files": accept_multiple_files,
        "key": key,
        "disabled": disabled,
    }
    if max_upload_size is not None and FILE_UPLOADER_SUPPORTS_MAX_UPLOAD_SIZE:
        kwargs["max_upload_size"] = max_upload_size
    return st.file_uploader(**kwargs)


def active_encryption_version(data: dict[str, Any] | None = None) -> int:
    if data is None:
        data = getattr(st.session_state, "data", {})
    encryption = data.get("encryption", {}) if isinstance(data, dict) else {}
    try:
        return max(1, int(encryption.get("active_key_version", 1)))
    except (TypeError, ValueError):
        return 1


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def private_chat_id(first_user: str, second_user: str) -> str:
    return "::".join(sorted([first_user, second_user]))


def group_chat_id(group_id: str) -> str:
    return f"{GROUP_PREFIX}{group_id}"


def is_group_conversation(conversation_id: str) -> bool:
    return conversation_id.startswith(GROUP_PREFIX)


def safe_key(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value)


def initials(name: str) -> str:
    parts = [part[0] for part in name.split() if part]
    return "".join(parts[:2]).upper() or "U"


def accent_for_username(username: str) -> str:
    return ACCENTS[sum(ord(char) for char in username) % len(ACCENTS)]


def default_email_for_username(username: str) -> str:
    return SEED_EMAILS.get(username, f"{username}@chatlite.local")


def crypto_available() -> bool:
    return bool(Fernet and rsa and serialization and hashes and asymmetric_padding)


def password_encryption_key(username: str, password: str, salt_hex: str) -> bytes:
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        salt = salt_hex.encode("utf-8")
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        b"chatlite-user-key:" + username.encode("utf-8") + b":" + salt,
        240_000,
    )
    return base64.urlsafe_b64encode(digest)


def generate_user_encryption_identity(username: str, password: str, salt_hex: str) -> dict[str, str]:
    if not crypto_available():
        return {"public_key": "", "encrypted_private_key": ""}
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    locker = Fernet(password_encryption_key(username, password, salt_hex))
    return {
        "public_key": public_pem.decode("ascii"),
        "encrypted_private_key": locker.encrypt(private_pem).decode("ascii"),
    }


def ensure_user_encryption_identity(username: str, password: str) -> bool:
    user = get_user(username)
    if not user or not crypto_available():
        return False
    user.setdefault("encryption_salt", uuid.uuid4().hex)
    if user.get("public_key") and user.get("encrypted_private_key"):
        return True
    user.update(generate_user_encryption_identity(username, password, user["encryption_salt"]))
    save_data(st.session_state.data)
    return bool(user.get("public_key") and user.get("encrypted_private_key"))


def reset_user_encryption_identity(username: str, password: str) -> None:
    user = get_user(username)
    if not user or not crypto_available():
        return
    user["encryption_salt"] = uuid.uuid4().hex
    user.update(generate_user_encryption_identity(username, password, user["encryption_salt"]))


def unlock_user_private_key(username: str, password: str) -> bool:
    if not ensure_user_encryption_identity(username, password):
        return False
    user = get_user(username)
    if not user:
        return False
    try:
        locker = Fernet(password_encryption_key(username, password, user.get("encryption_salt", "")))
        private_pem = locker.decrypt(user.get("encrypted_private_key", "").encode("ascii"))
        private_key = serialization.load_pem_private_key(private_pem, password=None)
    except (InvalidToken, ValueError, TypeError, UnicodeEncodeError):
        return False
    st.session_state.setdefault("private_keys", {})[username] = private_key
    return True


def current_private_key(username: str) -> Any | None:
    return st.session_state.get("private_keys", {}).get(username)


def encrypt_for_member(username: str, payload: bytes) -> str:
    user = get_user(username)
    public_pem = user.get("public_key", "") if user else ""
    if not public_pem or not crypto_available():
        return ""
    try:
        public_key = serialization.load_pem_public_key(public_pem.encode("ascii"))
        encrypted = public_key.encrypt(
            payload,
            asymmetric_padding.OAEP(
                mgf=asymmetric_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return base64.b64encode(encrypted).decode("ascii")
    except (ValueError, TypeError, UnicodeEncodeError):
        return ""


def decrypt_for_member(username: str, encrypted_payload: str) -> bytes:
    private_key = current_private_key(username)
    if not private_key or not encrypted_payload or not crypto_available():
        return b""
    try:
        return private_key.decrypt(
            base64.b64decode(encrypted_payload),
            asymmetric_padding.OAEP(
                mgf=asymmetric_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
    except (binascii.Error, ValueError, TypeError):
        return b""


def conversation_key_record(conversation_id: str, key_bytes: bytes, members: list[str], key_id: str | None = None) -> dict[str, Any]:
    key_id = key_id or uuid.uuid4().hex
    envelopes = {
        member: envelope
        for member in members
        if (envelope := encrypt_for_member(member, key_bytes))
    }
    return {
        "id": key_id,
        "algorithm": "rsa-oaep-fernet-v1",
        "created_at": current_stamp(),
        "updated_at": current_stamp(),
        "members": envelopes,
    }


def conversation_key_bundle(conversation_id: str) -> dict[str, Any] | None:
    key_store = st.session_state.data.setdefault("conversation_keys", {})
    bundle = key_store.get(conversation_id)
    if not bundle:
        return None
    if "keys" not in bundle:
        key_id = bundle.get("id") or "legacy"
        bundle["id"] = key_id
        key_store[conversation_id] = {"active_key_id": key_id, "keys": {key_id: bundle}}
    return key_store.get(conversation_id)


def conversation_key_for_user(
    conversation_id: str,
    username: str,
    create: bool = False,
    key_id: str | None = None,
) -> tuple[bytes, str]:
    if not crypto_available():
        return b"", ""
    key_store = st.session_state.data.setdefault("conversation_keys", {})
    bundle = conversation_key_bundle(conversation_id)
    key_bytes = b""
    resolved_key_id = ""
    if bundle:
        resolved_key_id = key_id or bundle.get("active_key_id", "")
        record = bundle.get("keys", {}).get(resolved_key_id, {})
        key_bytes = decrypt_for_member(username, record.get("members", {}).get(username, ""))
    elif create:
        resolved_key_id = uuid.uuid4().hex
        key_bytes = Fernet.generate_key()
        record = conversation_key_record(
            conversation_id,
            key_bytes,
            conversation_members_from_data(st.session_state.data, conversation_id),
            resolved_key_id,
        )
        key_store[conversation_id] = {"active_key_id": resolved_key_id, "keys": {resolved_key_id: record}}
        bundle = key_store[conversation_id]

    if create and bundle and not key_bytes:
        resolved_key_id = uuid.uuid4().hex
        key_bytes = Fernet.generate_key()
        record = conversation_key_record(
            conversation_id,
            key_bytes,
            conversation_members_from_data(st.session_state.data, conversation_id),
            resolved_key_id,
        )
        bundle.setdefault("keys", {})[resolved_key_id] = record
        bundle["active_key_id"] = resolved_key_id

    if create and bundle and key_bytes:
        changed = False
        record = bundle.setdefault("keys", {}).setdefault(
            resolved_key_id,
            conversation_key_record(conversation_id, key_bytes, [], resolved_key_id),
        )
        envelopes = record.setdefault("members", {})
        for member in conversation_members_from_data(st.session_state.data, conversation_id):
            if member not in envelopes:
                envelope = encrypt_for_member(member, key_bytes)
                if envelope:
                    envelopes[member] = envelope
                    changed = True
        if changed:
            record["updated_at"] = current_stamp()
    return key_bytes, resolved_key_id


def conversation_cipher(
    conversation_id: str,
    create: bool = False,
    key_id: str | None = None,
) -> tuple[Any | None, str]:
    username = st.session_state.get("current_user", "")
    key_bytes, resolved_key_id = conversation_key_for_user(conversation_id, username, create=create, key_id=key_id) if username else (b"", "")
    return (Fernet(key_bytes), resolved_key_id) if key_bytes and Fernet else (None, resolved_key_id)


def members_missing_public_keys(conversation_id: str) -> list[str]:
    missing = []
    for member in conversation_members_from_data(st.session_state.data, conversation_id):
        user = get_user(member)
        if not user or not user.get("public_key"):
            missing.append(member)
    return missing


def create_fresh_conversation_cipher(conversation_id: str) -> tuple[Any | None, str]:
    if not crypto_available():
        return None, ""
    key_bytes = Fernet.generate_key()
    key_id = uuid.uuid4().hex
    record = conversation_key_record(
        conversation_id,
        key_bytes,
        conversation_members_from_data(st.session_state.data, conversation_id),
        key_id,
    )
    bundle = conversation_key_bundle(conversation_id)
    if not bundle:
        st.session_state.data.setdefault("conversation_keys", {})[conversation_id] = {
            "active_key_id": key_id,
            "keys": {key_id: record},
        }
    else:
        bundle.setdefault("keys", {})[key_id] = record
        bundle["active_key_id"] = key_id
    return Fernet(key_bytes), key_id


def legacy_chat_cipher(conversation_id: str, key_version: int | None = None) -> Any | None:
    if not Fernet:
        return None
    if key_version is None:
        key_version = active_encryption_version()
    if key_version <= 0:
        key_material = f"{APP_SECRET}:{conversation_id}"
    else:
        key_material = f"{APP_SECRET}:{conversation_id}:v{key_version}"
    digest = hashlib.sha256(key_material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encryption_status_label() -> str:
    if not crypto_available():
        return "Encryption unavailable"
    current_user = st.session_state.get("current_user", "")
    if current_user and current_private_key(current_user):
        return f"End-to-end encrypted storage v{active_encryption_version()}"
    return "Encryption locked"


def encrypted_message_payload(
    conversation_id: str,
    text: str,
    key_version: int | None = None,
) -> dict[str, Any]:
    cipher, conversation_key_id = conversation_cipher(conversation_id, create=True)
    return encrypted_payload_with_cipher(text, active_encryption_version() if key_version is None else key_version, cipher, conversation_key_id)


def encrypted_payload_with_cipher(
    text: str,
    key_version: int,
    cipher: Any | None,
    conversation_key_id: str = "",
) -> dict[str, Any]:
    raw = text.encode("utf-8")
    compressed = zlib.compress(raw, level=6)
    use_compression = len(compressed) + 12 < len(raw)
    payload = compressed if use_compression else raw
    if not cipher:
        if use_compression:
            return {
                "text_payload": base64.b64encode(payload).decode("ascii"),
                "compressed": True,
                "encrypted": False,
                "key_version": key_version,
            }
        return {"text": text, "compressed": False, "encrypted": False, "key_version": key_version}
    token = cipher.encrypt(payload).decode("ascii")
    return {
        "ciphertext": token,
        "encrypted": True,
        "compressed": use_compression,
        "algorithm": "recipient-envelope-fernet-v1",
        "key_version": key_version,
        "conversation_key_id": conversation_key_id,
    }


def message_text(conversation_id: str, message: dict[str, Any]) -> str:
    if message.get("deleted"):
        return "This message was deleted."
    if not message.get("encrypted"):
        if message.get("compressed") and message.get("text_payload"):
            try:
                compressed = base64.b64decode(message.get("text_payload", ""))
                return zlib.decompress(compressed).decode("utf-8")
            except (binascii.Error, ValueError, zlib.error, UnicodeDecodeError):
                return "Compressed message could not be decoded"
        return message.get("text", "")

    if message.get("algorithm") == "recipient-envelope-fernet-v1":
        cipher, _ = conversation_cipher(conversation_id, create=False, key_id=message.get("conversation_key_id"))
    else:
        cipher = legacy_chat_cipher(conversation_id, safe_int(message.get("key_version"), 0))
    if not cipher:
        return "Encrypted message unavailable"
    try:
        decrypted = cipher.decrypt(message.get("ciphertext", "").encode("ascii"))
        if message.get("compressed"):
            decrypted = zlib.decompress(decrypted)
        return decrypted.decode("utf-8")
    except (InvalidToken, UnicodeEncodeError, UnicodeDecodeError, ValueError, zlib.error):
        return "Encrypted message could not be decrypted"


def country_name_for_region(region: str) -> str:
    if pycountry:
        country = pycountry.countries.get(alpha_2=region)
        if country:
            return country.name
    return region


def build_country_code_options() -> list[dict[str, str]]:
    if not phonenumbers:
        return FALLBACK_COUNTRY_CODES

    options = []
    for region in sorted(phonenumbers.SUPPORTED_REGIONS):
        code = phonenumbers.country_code_for_region(region)
        if not code:
            continue
        options.append(
            {
                "label": f"{country_name_for_region(region)} (+{code})",
                "code": f"+{code}",
                "region": region,
            }
        )
    return options or FALLBACK_COUNTRY_CODES


COUNTRY_CODE_OPTIONS = build_country_code_options()


def country_option_index(user: dict[str, Any]) -> int:
    user_region = user.get("country_region")
    user_code = user.get("country_code", "+91")
    for index, option in enumerate(COUNTRY_CODE_OPTIONS):
        if user_region and option["region"] == user_region:
            return index
    for index, option in enumerate(COUNTRY_CODE_OPTIONS):
        if option["code"] == user_code:
            return index
    return 0


def make_user(
    username: str,
    display_name: str,
    password: str,
    email: str | None = None,
    friends: list[str] | None = None,
) -> dict[str, Any]:
    encryption_salt = uuid.uuid4().hex
    encryption_identity = generate_user_encryption_identity(username, password, encryption_salt)
    return {
        "username": username,
        "display_name": display_name.strip() or username,
        "password_hash": password_hash(username, password),
        "encryption_salt": encryption_salt,
        "public_key": encryption_identity.get("public_key", ""),
        "encrypted_private_key": encryption_identity.get("encrypted_private_key", ""),
        "status": "available",
        "accent": accent_for_username(username),
        "accent_color": "#04986d",
        "theme": "Light",
        "email": normalize_email(email or default_email_for_username(username)),
        "country_code": "+91",
        "country_region": "IN",
        "phone_number": "",
        "photo_data_uri": "",
        "friends": sorted(friends or []),
        "blocked_users": [],
        "reported_users": [],
        "pinned_chats": [],
        "archived_chats": [],
        "last_seen_at": "",
        "online_until": "",
        "password_reset": {},
    }


def build_seed_data() -> dict[str, Any]:
    users = {
        "demo": make_user("demo", "Demo User", "demo123", SEED_EMAILS["demo"], ["aisha"]),
        "aisha": make_user("aisha", "Aisha Khan", "demo123", SEED_EMAILS["aisha"], ["demo", "michael"]),
        "michael": make_user("michael", "Michael Ross", "demo123", SEED_EMAILS["michael"], ["aisha"]),
        "nina": make_user("nina", "Nina Patel", "demo123", SEED_EMAILS["nina"], []),
    }
    group_id = "project-crew"
    return {
        "schema_version": 5,
        "users": users,
        "groups": {
            group_id: {
                "id": group_id,
                "name": "Project Crew",
                "admin": "demo",
                "members": ["demo", "aisha", "michael"],
                "roles": {"demo": "owner", "aisha": "member", "michael": "member"},
                "photo_data_uri": "",
                "accent": "#2f80ed",
                "created_at": "2026-06-07T08:00:00",
            }
        },
        "friend_requests": [
            {
                "id": "seed-request-nina-demo",
                "from": "nina",
                "to": "demo",
                "created_at": "2026-06-07T09:00:00",
            }
        ],
        "reports": [],
        "typing": {},
        "attachments": {},
        "rate_limits": {},
        "backups": [],
        "calls": [],
        "device_sessions": {},
        "scheduled_messages": [],
        "moderation_queue": [],
        "push_notifications": [],
        "offline_queue": {},
        "encryption": {"active_key_version": 1, "rotations": []},
        "messages": {
            private_chat_id("demo", "aisha"): [
                {
                    "id": "seed-demo-aisha-1",
                    "sender": "aisha",
                    "text": "Hey, welcome to ChatLite.",
                    "time": "10:14",
                    "created_at": "2026-06-07T10:14:00",
                },
                {
                    "id": "seed-demo-aisha-2",
                    "sender": "demo",
                    "text": "Thanks. The WhatsApp-style layout looks clean.",
                    "time": "10:18",
                    "created_at": "2026-06-07T10:18:00",
                },
            ],
            group_chat_id(group_id): [
                {
                    "id": "seed-group-1",
                    "sender": "michael",
                    "text": "I created a demo group chat for testing.",
                    "time": "11:02",
                    "created_at": "2026-06-07T11:02:00",
                }
            ],
        },
    }


def conversation_members_from_data(data: dict[str, Any], conversation_id: str) -> list[str]:
    if is_group_conversation(conversation_id):
        group_id = conversation_id.removeprefix(GROUP_PREFIX)
        group = data.get("groups", {}).get(group_id, {})
        return sorted(set(group.get("members", [])))
    return sorted(part for part in conversation_id.split("::") if part)


def message_state_from_lists(message: dict[str, Any], members: list[str]) -> str:
    if message.get("deleted"):
        return "deleted"
    if message.get("edited_at"):
        return "edited"
    sender = message.get("sender", "")
    others = [member for member in members if member != sender]
    if others and all(member in message.get("read_by", []) for member in others):
        return "read"
    if any(member in message.get("delivered_to", []) for member in others):
        return "delivered"
    return "sent"


def ensure_data_shape(data: dict[str, Any]) -> dict[str, Any]:
    previous_version = safe_int(data.get("schema_version"), 1)
    data["schema_version"] = 5
    data.setdefault("users", {})
    data.setdefault("groups", {})
    data.setdefault("friend_requests", [])
    data.setdefault("messages", {})
    data.setdefault("reports", [])
    data.setdefault("typing", {})
    data.setdefault("attachments", {})
    data.setdefault("rate_limits", {})
    data.setdefault("backups", [])
    data.setdefault("calls", [])
    data.setdefault("device_sessions", {})
    data.setdefault("scheduled_messages", [])
    data.setdefault("moderation_queue", [])
    data.setdefault("push_notifications", [])
    data.setdefault("offline_queue", {})
    data.setdefault("conversation_keys", {})
    encryption = data.setdefault("encryption", {})
    encryption.setdefault("active_key_version", 1)
    encryption.setdefault("rotations", [])

    seen_emails: set[str] = set()
    for username, user in data["users"].items():
        user.setdefault("username", username)
        user.setdefault("display_name", username)
        user.setdefault("status", "available")
        user.setdefault("accent", accent_for_username(username))
        user.setdefault("accent_color", "#04986d")
        user.setdefault("theme", "Light")
        email = normalize_email(user.get("email") or default_email_for_username(username))
        if not EMAIL_PATTERN.fullmatch(email):
            email = default_email_for_username(username)
        if email in seen_emails:
            email = f"{username}.{uuid.uuid4().hex[:6]}@chatlite.local"
        user["email"] = email
        seen_emails.add(email)
        user.setdefault("country_code", "+91")
        user.setdefault("country_region", "IN")
        user.setdefault("phone_number", "")
        user.setdefault("photo_data_uri", "")
        user["friends"] = sorted(set(user.get("friends", [])))
        user["blocked_users"] = sorted(set(user.get("blocked_users", [])))
        user["reported_users"] = sorted(set(user.get("reported_users", [])))
        user["pinned_chats"] = sorted(set(user.get("pinned_chats", [])))
        user["archived_chats"] = sorted(set(user.get("archived_chats", [])))
        user["starred_messages"] = sorted(set(user.get("starred_messages", [])))
        user["saved_messages"] = sorted(set(user.get("saved_messages", [])))
        user.setdefault("notification_keywords", [])
        user.setdefault("trust_score", 80)
        user.setdefault("abuse_score", 0)
        user.setdefault("last_login_at", "")
        user.setdefault("last_login_ip", "")
        user.setdefault("last_seen_at", "")
        user.setdefault("online_until", "")
        user.setdefault("password_reset", {})
        user.setdefault("encryption_salt", uuid.uuid4().hex)
        user.setdefault("public_key", "")
        user.setdefault("encrypted_private_key", "")

    for group_id, group in data["groups"].items():
        group.setdefault("id", group_id)
        group.setdefault("name", "Group chat")
        group.setdefault("admin", next(iter(group.get("members", [])), ""))
        group["members"] = sorted(set(group.get("members", [])))
        if group.get("admin") not in group["members"]:
            group["admin"] = next(iter(group["members"]), "")
        roles = group.setdefault("roles", {})
        admin = group.get("admin", "")
        for member in group["members"]:
            roles.setdefault(member, "member")
        if admin:
            roles[admin] = "owner"
        for member in list(roles):
            if member not in group["members"]:
                roles.pop(member, None)
            elif roles[member] not in {"owner", "admin", "member", "muted"}:
                roles[member] = "member"
        group.setdefault("photo_data_uri", "")
        group.setdefault("accent", "#2f80ed")
        group.setdefault("created_at", current_stamp())
        group.setdefault("invite_code", uuid.uuid4().hex[:10])
        group.setdefault("approval_required", False)
        group.setdefault("join_requests", [])

    for conversation_id, messages in data["messages"].items():
        members = conversation_members_from_data(data, conversation_id)
        for message in messages:
            sender = message.get("sender", "")
            message.setdefault("id", str(uuid.uuid4()))
            message.setdefault("time", current_time())
            message.setdefault("created_at", current_stamp())
            message.setdefault("attachments", [])
            message.setdefault("edited_at", "")
            message.setdefault("deleted_at", "")
            message.setdefault("deleted", False)
            message.setdefault("expires_at", "")
            message.setdefault("reply_to", "")
            message.setdefault("forwarded_from", "")
            message.setdefault("starred_by", [])
            message.setdefault("reactions", {})
            message.setdefault("poll", None)
            message.setdefault("conflict_version", 1)
            message.setdefault("topic_labels", [])
            message.setdefault("duplicate_cluster_id", "")
            message.setdefault("moderation_flags", [])
            message.setdefault("spam_score", 0)
            message.setdefault("compressed", False)
            message.setdefault("conversation_key_id", "")
            if message.get("encrypted"):
                message.setdefault("key_version", 0)
            else:
                message.setdefault("encrypted", False)
                message.setdefault("key_version", 0)
            message.setdefault(
                "delivered_to",
                [member for member in members if member != sender and member in message.get("read_by", [])],
            )
            if previous_version < 3:
                message.setdefault("read_by", members)
            else:
                message.setdefault("read_by", [sender])
            message["state"] = message_state_from_lists(message, members)

    for attachment_hash, asset in data["attachments"].items():
        asset.setdefault("hash", attachment_hash)
        if "storage_backend" not in asset:
            asset["storage_backend"] = "local" if asset.get("payload") else OBJECT_STORAGE_PROVIDER
        asset.setdefault("object_key", "")
        asset.setdefault("object_size", 0)
        asset.setdefault("scan_status", "clean")
        asset.setdefault("thumbnail_data_uri", "")

    for call in data["calls"]:
        call.setdefault("id", str(uuid.uuid4()))
        call.setdefault("conversation_id", "")
        call.setdefault("caller", "")
        call.setdefault("type", "voice")
        call.setdefault("status", "completed")
        call.setdefault("started_at", current_stamp())
        call.setdefault("ended_at", "")
        call.setdefault("participants", [])

    for scheduled in data["scheduled_messages"]:
        scheduled.setdefault("id", str(uuid.uuid4()))
        scheduled.setdefault("sender", "")
        scheduled.setdefault("conversation_id", "")
        scheduled.setdefault("text", "")
        scheduled.setdefault("send_at", current_stamp())
        scheduled.setdefault("created_at", current_stamp())
        scheduled.setdefault("status", "pending")
        scheduled.setdefault("reply_to", "")
        scheduled.setdefault("expires_at", "")

    for username in data["users"]:
        data["device_sessions"].setdefault(username, [])
        data["offline_queue"].setdefault(username, [])

    return data


def selected_backend() -> str:
    if STORAGE_BACKEND in {"json", "sqlite", "postgres"}:
        return STORAGE_BACKEND
    if DATABASE_URL.startswith(("postgresql://", "postgres://")):
        return "postgres"
    return "sqlite"


def active_storage_backend() -> str:
    return getattr(st.session_state, "storage_backend_active", selected_backend())


def sqlite_path() -> Path:
    if DATABASE_URL.startswith("sqlite:///"):
        path_text = unquote(DATABASE_URL.removeprefix("sqlite:///"))
        if path_text:
            return Path(path_text).expanduser()
    return SQLITE_FILE


def read_json_state() -> dict[str, Any] | None:
    if not LEGACY_DATA_FILE.exists():
        return None
    try:
        return json.loads(LEGACY_DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_json_state(data: dict[str, Any]) -> None:
    LEGACY_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    LEGACY_DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_sqlite_state() -> dict[str, Any] | None:
    path = sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS chatlite_state "
            "(id INTEGER PRIMARY KEY CHECK (id = 1), data TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        row = conn.execute("SELECT data FROM chatlite_state WHERE id = 1").fetchone()
    if not row:
        return None
    return json.loads(row[0])


def write_sqlite_state(data: dict[str, Any]) -> None:
    path = sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS chatlite_state "
            "(id INTEGER PRIMARY KEY CHECK (id = 1), data TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO chatlite_state (id, data, updated_at) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
            (payload, current_stamp()),
        )
        conn.commit()


def read_postgres_state() -> dict[str, Any] | None:
    if not psycopg:
        raise RuntimeError("PostgreSQL storage requires psycopg. Run: pip install -r requirements.txt")
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS chatlite_state "
                "(id INTEGER PRIMARY KEY, data JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
            cur.execute("SELECT data FROM chatlite_state WHERE id = 1")
            row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    return row[0] if isinstance(row[0], dict) else json.loads(row[0])


def write_postgres_state(data: dict[str, Any]) -> None:
    if not psycopg:
        raise RuntimeError("PostgreSQL storage requires psycopg. Run: pip install -r requirements.txt")
    payload = Jsonb(data) if Jsonb else json.dumps(data)
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS chatlite_state "
                "(id INTEGER PRIMARY KEY, data JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
            cur.execute(
                "INSERT INTO chatlite_state (id, data, updated_at) VALUES (1, %s, now()) "
                "ON CONFLICT (id) DO UPDATE SET data = excluded.data, updated_at = now()",
                (payload,),
            )
        conn.commit()


def load_data() -> dict[str, Any]:
    backend = selected_backend()
    save_backend = backend
    try:
        if backend == "json":
            loaded = read_json_state()
        elif backend == "postgres":
            loaded = read_postgres_state()
        else:
            loaded = read_sqlite_state()
    except Exception as exc:
        st.error(f"Storage error: {exc}")
        save_backend = "sqlite"
        try:
            loaded = read_sqlite_state() or read_json_state()
        except Exception:
            loaded = None

    if not loaded and save_backend == "sqlite":
        loaded = read_json_state()
    shaped_data = ensure_data_shape(loaded or build_seed_data())
    st.session_state.storage_backend_active = save_backend
    try:
        save_data(shaped_data, backend=save_backend)
    except Exception as exc:
        st.error(f"Storage save error: {exc}")
    return shaped_data


def save_data(data: dict[str, Any], backend: str | None = None) -> None:
    backend = backend or active_storage_backend()
    if backend == "json":
        write_json_state(data)
    elif backend == "postgres":
        write_postgres_state(data)
    else:
        write_sqlite_state(data)


def get_user(username: str) -> dict[str, Any] | None:
    return st.session_state.data["users"].get(username)


def get_group(group_id: str) -> dict[str, Any] | None:
    return st.session_state.data["groups"].get(group_id)


def rate_limit_identity(identity: str, action: str) -> str:
    digest = hashlib.sha256(identity.strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"{action}:{digest}"


def check_rate_limit(identity: str, action: str) -> tuple[bool, str]:
    limit, window_seconds = RATE_LIMIT_RULES.get(action, (20, 60))
    if action in {"message", "friend_request"}:
        username = (identity or "").split(":", 1)[0]
        trust = user_trust_score(username)
        if trust < 30:
            limit = max(2, limit // 3)
        elif trust < 60:
            limit = max(3, limit // 2)
        elif trust > 90:
            limit = int(limit * 1.25)
    key = rate_limit_identity(identity or "anonymous", action)
    now = datetime.now()
    cutoff = now - timedelta(seconds=window_seconds)
    buckets = st.session_state.data.setdefault("rate_limits", {})
    timestamps = []
    for stamp in buckets.get(key, []):
        parsed = parse_stamp(stamp)
        if parsed and parsed >= cutoff:
            timestamps.append(stamp)
    if len(timestamps) >= limit:
        reset_at = parse_stamp(timestamps[0])
        wait_seconds = window_seconds
        if reset_at:
            wait_seconds = max(1, int((reset_at + timedelta(seconds=window_seconds) - now).total_seconds()))
        buckets[key] = timestamps
        save_data(st.session_state.data)
        wait_minutes = max(1, (wait_seconds + 59) // 60)
        return False, f"Rate limit reached for {action.replace('_', ' ')}. Try again in {wait_minutes} minute(s)."
    timestamps.append(now.isoformat(timespec="seconds"))
    buckets[key] = timestamps
    save_data(st.session_state.data)
    return True, ""


def clear_rate_limit(identity: str, action: str) -> None:
    key = rate_limit_identity(identity or "anonymous", action)
    buckets = st.session_state.data.setdefault("rate_limits", {})
    if key in buckets:
        buckets.pop(key, None)
        save_data(st.session_state.data)


def message_ref(conversation_id: str, message_id: str) -> str:
    return f"{conversation_id}::{message_id}"


def fuzzy_ratio(first: str, second: str) -> float:
    first = first.strip().lower()
    second = second.strip().lower()
    if not first or not second:
        return 0.0
    return SequenceMatcher(None, first, second).ratio()


def user_trust_score(username: str) -> int:
    user = get_user(username)
    if not user:
        return 50
    trust = safe_int(user.get("trust_score"), 80)
    abuse = safe_int(user.get("abuse_score"), 0)
    return max(5, min(100, trust - abuse))


def update_user_reputation(username: str, spam_score: int, flags: list[str]) -> None:
    user = get_user(username)
    if not user:
        return
    if spam_score >= 70 or flags:
        user["abuse_score"] = min(100, safe_int(user.get("abuse_score"), 0) + 3 + len(flags))
        user["trust_score"] = max(5, safe_int(user.get("trust_score"), 80) - 1)
    else:
        user["trust_score"] = min(100, safe_int(user.get("trust_score"), 80) + 1)


def topic_labels_for_text(text: str) -> list[str]:
    words = set(text_words(text))
    labels = [label for label, keywords in TOPIC_KEYWORDS.items() if words & keywords]
    return labels or ["general"]


def toxicity_score(text: str) -> int:
    words = set(text_words(text))
    score = 0
    score += min(60, len(words & DEFAULT_BLOCKED_WORDS) * 25)
    if re.search(r"(.)\1{8,}", text):
        score += 10
    if any(term in text.lower() for term in ["threat", "attack", "harass"]):
        score += 20
    return min(100, score)


def duplicate_cluster_id(conversation_id: str, sender: str, text: str) -> str:
    normalized = " ".join(text_words(text))[:160]
    if not normalized:
        return ""
    digest = hashlib.sha256(f"{conversation_id}:{sender}:{normalized}".encode("utf-8")).hexdigest()
    return digest[:12]


def find_message(conversation_id: str, message_id: str) -> dict[str, Any] | None:
    return next(
        (message for message in st.session_state.data["messages"].get(conversation_id, []) if message.get("id") == message_id),
        None,
    )


def message_preview(conversation_id: str, message: dict[str, Any] | None, limit: int = 80) -> str:
    if not message:
        return "Message unavailable"
    text = message_text(conversation_id, message)
    if message.get("poll"):
        text = f"Poll: {message['poll'].get('question', '')}"
    if message.get("attachments") and not text:
        text = f"{len(message.get('attachments', []))} attachment(s)"
    return text[:limit] or "Message"


def expiry_from_seconds(seconds: int) -> str:
    if seconds <= 0:
        return ""
    return (datetime.now() + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def is_expired_message(message: dict[str, Any]) -> bool:
    expires_at = parse_stamp(message.get("expires_at"))
    return bool(expires_at and expires_at <= datetime.now() and not message.get("deleted"))


def clean_expired_messages() -> None:
    changed = False
    for messages in st.session_state.data.get("messages", {}).values():
        for message in messages:
            if is_expired_message(message):
                message["deleted"] = True
                message["deleted_at"] = current_stamp()
                message["state"] = "deleted"
                message["attachments"] = []
                message.pop("text", None)
                message.pop("text_payload", None)
                message.pop("ciphertext", None)
                changed = True
    if changed:
        save_data(st.session_state.data)


def flush_offline_queue(username: str) -> None:
    queue = st.session_state.data.setdefault("offline_queue", {}).setdefault(username, [])
    changed = False
    for item in queue:
        if item.get("status") == "queued":
            item["status"] = "delivered"
            item["delivered_at"] = current_stamp()
            changed = True
    if changed:
        save_data(st.session_state.data)


def scan_attachment_bytes(file_bytes: bytes, filename: str, mime_type: str) -> tuple[str, list[str]]:
    lowered = filename.lower()
    issues = []
    if b"X5O!P%@AP" in file_bytes or b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in file_bytes:
        issues.append("EICAR test signature")
    if lowered.endswith((".exe", ".bat", ".cmd", ".scr", ".js", ".vbs", ".ps1")):
        issues.append("Executable attachment")
    if mime_type == "application/octet-stream" and "." not in filename:
        issues.append("Unknown binary file")
    return ("blocked" if issues else "clean", issues)


def thumbnail_for_attachment(file_bytes: bytes, mime_type: str) -> str:
    if not mime_type.startswith("image/") or len(file_bytes) > 220_000:
        return ""
    encoded = base64.b64encode(file_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def send_push_notification(username: str, title: str, body: str, conversation_id: str = "") -> None:
    status = "local"
    if ONESIGNAL_APP_ID and ONESIGNAL_API_KEY:
        try:
            import requests

            response = requests.post(
                "https://onesignal.com/api/v1/notifications",
                headers={"Authorization": f"Basic {ONESIGNAL_API_KEY}", "Content-Type": "application/json"},
                json={
                    "app_id": ONESIGNAL_APP_ID,
                    "included_segments": ["Subscribed Users"],
                    "headings": {"en": title},
                    "contents": {"en": body},
                    "data": {"username": username, "conversation_id": conversation_id},
                },
                timeout=5,
            )
            status = "sent" if response.ok else "failed"
        except Exception:
            status = "failed"
    elif FIREBASE_CREDENTIALS_FILE:
        try:
            firebase_admin = importlib.import_module("firebase_admin")
            credentials = importlib.import_module("firebase_admin.credentials")
            messaging = importlib.import_module("firebase_admin.messaging")

            if not getattr(firebase_admin, "_apps", None):
                firebase_admin.initialize_app(credentials.Certificate(FIREBASE_CREDENTIALS_FILE))
            messaging.send(
                messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    topic=FIREBASE_TOPIC,
                    data={"username": username, "conversation_id": conversation_id},
                )
            )
            status = "sent"
        except Exception:
            status = "failed"
    elif PUSH_WEBHOOK_URL:
        status = "queued"
    st.session_state.data.setdefault("push_notifications", []).append(
        {
            "id": str(uuid.uuid4()),
            "to": username,
            "title": title,
            "body": body,
            "conversation_id": conversation_id,
            "created_at": current_stamp(),
            "status": status,
        }
    )


def realtime_ws_url(conversation_id: str) -> str:
    if not REALTIME_WS_URL:
        return ""
    return f"{REALTIME_WS_URL}/{quote(conversation_id, safe='')}"


def realtime_publish_url(conversation_id: str) -> str:
    if not REALTIME_WS_URL:
        return ""
    if REALTIME_WS_URL.startswith("wss://"):
        base = "https://" + REALTIME_WS_URL.removeprefix("wss://")
    elif REALTIME_WS_URL.startswith("ws://"):
        base = "http://" + REALTIME_WS_URL.removeprefix("ws://")
    else:
        base = REALTIME_WS_URL
    if base.endswith("/ws"):
        base = base[:-3] + "/publish"
    else:
        base = f"{base.rstrip('/')}/publish"
    return f"{base}/{quote(conversation_id, safe='')}"


def notify_realtime_event(conversation_id: str, event_type: str, actor: str, message_id: str = "") -> None:
    publish_url = realtime_publish_url(conversation_id)
    if not publish_url:
        return
    try:
        requests = importlib.import_module("requests")
        requests.post(
            publish_url,
            json={
                "event": event_type,
                "actor": actor,
                "message_id": message_id,
                "created_at": current_stamp(),
            },
            timeout=2,
        )
    except Exception:
        return


def render_realtime_bridge(conversation_id: str, current_user: str) -> None:
    ws_url = realtime_ws_url(conversation_id)
    if not ws_url or components is None:
        return
    components.html(
        f"""
        <script>
        (() => {{
          const wsUrl = {json.dumps(ws_url)};
          const currentUser = {json.dumps(current_user)};
          const key = "chatlite-realtime-" + wsUrl;
          if (window.parent[key]) {{
            try {{ window.parent[key].close(); }} catch (error) {{}}
          }}
          const socket = new WebSocket(wsUrl);
          window.parent[key] = socket;
          socket.onmessage = (event) => {{
            try {{
              const envelope = JSON.parse(event.data || "{{}}");
              const payload = JSON.parse(envelope.payload || "{{}}");
              if (payload.actor && payload.actor !== currentUser) {{
                setTimeout(() => window.parent.location.reload(), 350);
              }}
            }} catch (error) {{}}
          }};
        }})();
        </script>
        """,
        height=1,
    )


def send_reset_email(email_value: str, code: str) -> bool:
    if not (SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD):
        return False
    message = EmailMessage()
    message["Subject"] = "ChatLite password reset code"
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = email_value
    message.set_content(f"Your ChatLite reset code is: {code}\n\nThis code expires in 15 minutes.")
    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
        smtp.starttls(context=context)
        smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.send_message(message)
    return True


def detect_login_anomaly(user: dict[str, Any]) -> list[str]:
    flags = []
    client_ip = os.getenv("CHATLITE_CLIENT_IP", "")
    previous_ip = user.get("last_login_ip", "")
    if client_ip and previous_ip and client_ip != previous_ip:
        flags.append("login from new client IP")
    hour = datetime.now().hour
    if user.get("last_login_at") and hour < 5:
        flags.append("unusual login hour")
    return flags


def create_device_session(username: str, label: str = "Web session") -> str:
    session_id = uuid.uuid4().hex
    sessions = st.session_state.data.setdefault("device_sessions", {}).setdefault(username, [])
    sessions.append(
        {
            "id": session_id,
            "label": label,
            "created_at": current_stamp(),
            "last_seen_at": current_stamp(),
            "active": True,
        }
    )
    return session_id


def touch_device_session(username: str) -> None:
    session_id = st.session_state.get("current_session_id", "")
    for session in st.session_state.data.setdefault("device_sessions", {}).setdefault(username, []):
        if session.get("id") == session_id:
            session["last_seen_at"] = current_stamp()
            session["active"] = True
            return


def logout_device(username: str, session_id: str) -> None:
    for session in st.session_state.data.setdefault("device_sessions", {}).setdefault(username, []):
        if session.get("id") == session_id:
            session["active"] = False
            session["ended_at"] = current_stamp()


def logout_all_devices(username: str) -> None:
    for session in st.session_state.data.setdefault("device_sessions", {}).setdefault(username, []):
        session["active"] = False
        session["ended_at"] = current_stamp()
    save_data(st.session_state.data)


def current_session_is_active(username: str) -> bool:
    session_id = st.session_state.get("current_session_id", "")
    if not session_id:
        return False
    sessions = st.session_state.data.setdefault("device_sessions", {}).setdefault(username, [])
    return any(session.get("id") == session_id and session.get("active") for session in sessions)


def start_call(username: str, conversation_id: str, call_type: str) -> tuple[bool, str]:
    if call_type not in CALL_TYPES:
        return False, "Choose voice or video."
    members = conversation_members(conversation_id)
    if username not in members:
        return False, "You are not a member of this chat."
    st.session_state.data.setdefault("calls", []).insert(
        0,
        {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "caller": username,
            "type": call_type,
            "status": "completed",
            "started_at": current_stamp(),
            "ended_at": current_stamp(),
            "participants": members,
        },
    )
    save_data(st.session_state.data)
    return True, f"{call_type.title()} call added to history."


def toggle_reaction(conversation_id: str, message_id: str, username: str, reaction: str) -> tuple[bool, str]:
    message = find_message(conversation_id, message_id)
    if not message or message.get("deleted"):
        return False, "Message not found."
    reactions = message.setdefault("reactions", {})
    users = set(reactions.get(reaction, []))
    if username in users:
        users.remove(username)
    else:
        users.add(username)
    if users:
        reactions[reaction] = sorted(users)
    else:
        reactions.pop(reaction, None)
    save_data(st.session_state.data)
    return True, "Reaction updated."


def toggle_star_message(conversation_id: str, message_id: str, username: str) -> tuple[bool, str]:
    message = find_message(conversation_id, message_id)
    user = get_user(username)
    if not message or not user:
        return False, "Message not found."
    ref = message_ref(conversation_id, message_id)
    starred = set(message.setdefault("starred_by", []))
    saved = set(user.get("starred_messages", []))
    if username in starred:
        starred.remove(username)
        saved.discard(ref)
        label = "Message unstarred."
    else:
        starred.add(username)
        saved.add(ref)
        label = "Message starred."
    message["starred_by"] = sorted(starred)
    user["starred_messages"] = sorted(saved)
    user["saved_messages"] = sorted(saved)
    save_data(st.session_state.data)
    return True, label


def forward_message(source_conversation_id: str, message_id: str, sender: str, target_conversation_id: str) -> tuple[bool, str]:
    source = find_message(source_conversation_id, message_id)
    if not source or source.get("deleted"):
        return False, "Message not found."
    text = message_text(source_conversation_id, source)
    attachments = source.get("attachments", [])
    success, message = add_message_to_conversation(
        sender,
        target_conversation_id,
        text,
        attachments=attachments,
        forwarded_from=message_ref(source_conversation_id, message_id),
    )
    return success, "Message forwarded." if success else message


def schedule_message(
    sender: str,
    conversation_id: str,
    text: str,
    send_at: datetime,
    reply_to: str = "",
    expires_at: str = "",
) -> tuple[bool, str]:
    if not text.strip():
        return False, "Scheduled message needs text."
    if send_at <= datetime.now():
        return False, "Choose a future time."
    st.session_state.data.setdefault("scheduled_messages", []).append(
        {
            "id": str(uuid.uuid4()),
            "sender": sender,
            "conversation_id": conversation_id,
            "text": text.strip(),
            "send_at": send_at.isoformat(timespec="seconds"),
            "created_at": current_stamp(),
            "status": "pending",
            "reply_to": reply_to,
            "expires_at": expires_at,
        }
    )
    save_data(st.session_state.data)
    return True, "Message scheduled."


def deliver_due_scheduled_messages() -> None:
    changed = False
    for scheduled in st.session_state.data.setdefault("scheduled_messages", []):
        if scheduled.get("status") != "pending":
            continue
        send_at = parse_stamp(scheduled.get("send_at"))
        if not send_at or send_at > datetime.now():
            continue
        success, _ = add_message_to_conversation(
            scheduled["sender"],
            scheduled["conversation_id"],
            scheduled["text"],
            reply_to=scheduled.get("reply_to", ""),
            expires_at=scheduled.get("expires_at", ""),
            skip_rate_limit=True,
        )
        scheduled["status"] = "sent" if success else "failed"
        scheduled["sent_at"] = current_stamp()
        changed = True
    if changed:
        save_data(st.session_state.data)


def create_poll_message(sender: str, conversation_id: str, question: str, options: list[str]) -> tuple[bool, str]:
    if not is_group_conversation(conversation_id):
        return False, "Polls are available in groups."
    cleaned_question = question.strip()
    cleaned_options = [option.strip() for option in options if option.strip()]
    if not cleaned_question or len(cleaned_options) < 2:
        return False, "Add a question and at least two options."
    success, message = add_message_to_conversation(
        sender,
        conversation_id,
        f"Poll: {cleaned_question}",
        poll={
            "question": cleaned_question,
            "options": [{"id": uuid.uuid4().hex[:8], "text": option, "votes": []} for option in cleaned_options[:6]],
            "closed": False,
        },
    )
    return success, "Poll created." if success else message


def vote_poll(conversation_id: str, message_id: str, option_id: str, username: str) -> tuple[bool, str]:
    message = find_message(conversation_id, message_id)
    poll = message.get("poll") if message else None
    if not poll or poll.get("closed"):
        return False, "Poll not available."
    for option in poll.get("options", []):
        option["votes"] = [vote for vote in option.get("votes", []) if vote != username]
    for option in poll.get("options", []):
        if option.get("id") == option_id:
            option.setdefault("votes", []).append(username)
            save_data(st.session_state.data)
            return True, "Vote saved."
    return False, "Poll option not found."


def request_group_join(invite_code: str, username: str) -> tuple[bool, str]:
    cleaned = invite_code.strip()
    group = next((item for item in st.session_state.data["groups"].values() if item.get("invite_code") == cleaned), None)
    if not group:
        return False, "Invite code not found."
    if username in group.get("members", []):
        return False, "You are already in this group."
    if group.get("approval_required"):
        requests = group.setdefault("join_requests", [])
        if any(request.get("username") == username and request.get("status") == "pending" for request in requests):
            return False, "Join request already pending."
        requests.append({"id": str(uuid.uuid4()), "username": username, "created_at": current_stamp(), "status": "pending"})
        save_data(st.session_state.data)
        return True, "Join request sent to group admins."
    group["members"] = sorted(set(group.get("members", [])) | {username})
    group.setdefault("roles", {})[username] = "member"
    save_data(st.session_state.data)
    return True, f"Joined {group.get('name', 'group')}."


def respond_group_join(group_id: str, request_id: str, approve: bool) -> tuple[bool, str]:
    group = get_group(group_id)
    if not group:
        return False, "Group not found."
    request = next((item for item in group.get("join_requests", []) if item.get("id") == request_id), None)
    if not request:
        return False, "Join request not found."
    request["status"] = "approved" if approve else "declined"
    request["resolved_at"] = current_stamp()
    username = request.get("username", "")
    if approve and username in st.session_state.data["users"]:
        group["members"] = sorted(set(group.get("members", [])) | {username})
        group.setdefault("roles", {})[username] = "member"
    save_data(st.session_state.data)
    return True, "Join request updated."


def import_contacts(current_user: str, raw_contacts: str) -> tuple[int, list[str]]:
    sent = 0
    messages = []
    for token in re.split(r"[\s,;]+", raw_contacts):
        token = token.strip()
        if not token:
            continue
        target = username_for_friend_identifier(token)
        if not target and PHONE_PATTERN.fullmatch(token):
            target = next(
                (
                    username
                    for username, user in st.session_state.data["users"].items()
                    if token.replace(" ", "") in user.get("phone_number", "").replace(" ", "")
                ),
                None,
            )
        if not target:
            messages.append(f"{token}: not found")
            continue
        success, message = send_friend_request(current_user, target)
        if success:
            sent += 1
        messages.append(f"{token}: {message}")
    return sent, messages


def export_chat_text(current_user: str, conversation_id: str) -> str:
    lines = [f"Chat export: {conversation_id}", f"Exported by @{current_user} at {current_stamp()}", ""]
    for message in st.session_state.data["messages"].get(conversation_id, []):
        if message.get("deleted"):
            continue
        sender = get_user(message.get("sender", ""))
        sender_name = sender["display_name"] if sender else message.get("sender", "Unknown")
        lines.append(f"[{message.get('created_at', '')}] {sender_name}: {message_preview(conversation_id, message, 500)}")
    return "\n".join(lines)


def export_chat_pdf_bytes(current_user: str, conversation_id: str) -> bytes:
    text = export_chat_text(current_user, conversation_id)
    safe_lines = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")[:110] for line in text.splitlines()]
    stream_lines = ["BT", "/F1 10 Tf", "50 780 Td"]
    for line in safe_lines[:70]:
        stream_lines.append(f"({line}) Tj")
        stream_lines.append("0 -14 Td")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        b"5 0 obj << /Length " + str(len(stream)).encode("ascii") + b" >> stream\n" + stream + b"\nendstream endobj",
    ]
    output = io.BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(output.tell())
        output.write(obj + b"\n")
    xref_at = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(f"trailer << /Root 1 0 R /Size {len(objects) + 1} >>\nstartxref\n{xref_at}\n%%EOF".encode("ascii"))
    return output.getvalue()


def user_activity_stats(username: str) -> dict[str, int]:
    sent = 0
    starred = len(get_user(username).get("starred_messages", [])) if get_user(username) else 0
    calls = sum(1 for call in st.session_state.data.get("calls", []) if username in call.get("participants", []))
    scheduled = sum(1 for item in st.session_state.data.get("scheduled_messages", []) if item.get("sender") == username and item.get("status") == "pending")
    for messages in st.session_state.data.get("messages", {}).values():
        sent += sum(1 for message in messages if message.get("sender") == username)
    return {"messages_sent": sent, "starred": starred, "calls": calls, "scheduled": scheduled}


def smart_reply_suggestions(current_user: str, conversation_id: str) -> list[str]:
    messages = [
        message
        for message in st.session_state.data["messages"].get(conversation_id, [])
        if message.get("sender") != current_user and not message.get("deleted")
    ]
    if not messages:
        return ["Hi", "Thanks", "Sure"]
    latest = message_text(conversation_id, messages[-1]).lower()
    if "?" in latest:
        return ["Yes, sounds good.", "Let me check and reply.", "Can you share more details?"]
    if any(word in latest for word in ["urgent", "asap", "blocked", "issue"]):
        return ["I am checking this now.", "Please send the details.", "I will update you shortly."]
    if any(word in latest for word in ["thanks", "thank you"]):
        return ["You are welcome.", "Happy to help.", "Anytime."]
    return ["Got it.", "Thanks for the update.", "I will check."]


def text_words(value: str) -> list[str]:
    return WORD_PATTERN.findall(value.lower())


def detect_content_issues(text: str) -> list[dict[str, str]]:
    cleaned = text.strip()
    if not cleaned:
        return []
    lowered = cleaned.lower()
    words = set(text_words(cleaned))
    urls = URL_PATTERN.findall(cleaned)
    issues: list[dict[str, str]] = []
    blocked_matches = sorted(words & DEFAULT_BLOCKED_WORDS)
    if blocked_matches:
        issues.append(
            {
                "code": "blocked_word",
                "label": f"Flagged words: {', '.join(blocked_matches[:3])}",
                "severity": "review",
            }
        )
    if len(urls) >= 3:
        issues.append({"code": "link_flood", "label": "Too many links", "severity": "block"})
    if urls and (SHORT_LINK_PATTERN.search(lowered) or any(term in lowered for term in ["verify", "password", "prize"])):
        issues.append({"code": "suspicious_link", "label": "Suspicious link pattern", "severity": "block"})
    if re.search(r"(.)\1{8,}", cleaned):
        issues.append({"code": "repeated_characters", "label": "Repeated characters", "severity": "review"})
    return issues


def spam_detection_score(sender: str, conversation_id: str, text: str, attachments: list[dict[str, Any]]) -> int:
    score = 0
    cleaned = text.strip().lower()
    if not cleaned and len(attachments) > 4:
        score += 35
    if len(URL_PATTERN.findall(text)) >= 2:
        score += 25
    if cleaned:
        recent_same_sender = [
            message
            for message in st.session_state.data["messages"].get(conversation_id, [])[-10:]
            if message.get("sender") == sender and not message.get("deleted")
        ]
        repeated = sum(1 for message in recent_same_sender if message_text(conversation_id, message).strip().lower() == cleaned)
        score += min(60, repeated * 30)
        word_counts = Counter(text_words(cleaned))
        if word_counts and word_counts.most_common(1)[0][1] >= 8:
            score += 20
    return min(100, score)


def compress_bytes(payload: bytes) -> tuple[bool, bytes]:
    compressed = zlib.compress(payload, level=6)
    if len(compressed) + 24 < len(payload):
        return True, compressed
    return False, payload


def upload_object_storage(object_key: str, payload: bytes, mime_type: str) -> tuple[str, str]:
    if OBJECT_STORAGE_PROVIDER not in {"s3", "minio"} or not OBJECT_STORAGE_BUCKET:
        return "", ""
    try:
        if OBJECT_STORAGE_PROVIDER == "s3":
            boto3 = importlib.import_module("boto3")

            client_kwargs = {}
            if OBJECT_STORAGE_ENDPOINT:
                client_kwargs["endpoint_url"] = OBJECT_STORAGE_ENDPOINT
            s3 = boto3.client("s3", **client_kwargs)
            s3.put_object(Bucket=OBJECT_STORAGE_BUCKET, Key=object_key, Body=payload, ContentType=mime_type)
            return OBJECT_STORAGE_PROVIDER, object_key
        minio_module = importlib.import_module("minio")
        Minio = getattr(minio_module, "Minio")

        endpoint = OBJECT_STORAGE_ENDPOINT.replace("https://", "").replace("http://", "")
        minio_client = Minio(
            endpoint,
            access_key=OBJECT_STORAGE_ACCESS_KEY,
            secret_key=OBJECT_STORAGE_SECRET_KEY,
            secure=OBJECT_STORAGE_ENDPOINT.startswith("https://"),
        )
        if not minio_client.bucket_exists(OBJECT_STORAGE_BUCKET):
            minio_client.make_bucket(OBJECT_STORAGE_BUCKET)
        minio_client.put_object(
            OBJECT_STORAGE_BUCKET,
            object_key,
            io.BytesIO(payload),
            length=len(payload),
            content_type=mime_type,
        )
        return OBJECT_STORAGE_PROVIDER, object_key
    except Exception:
        return "", ""


def download_object_storage(asset: dict[str, Any]) -> bytes:
    object_backend = asset.get("storage_backend", "")
    object_key = asset.get("object_key", "")
    if object_backend not in {"s3", "minio"} or not OBJECT_STORAGE_BUCKET or not object_key:
        return b""
    try:
        if object_backend == "s3":
            boto3 = importlib.import_module("boto3")
            client_kwargs = {}
            if OBJECT_STORAGE_ENDPOINT:
                client_kwargs["endpoint_url"] = OBJECT_STORAGE_ENDPOINT
            s3 = boto3.client("s3", **client_kwargs)
            response = s3.get_object(Bucket=OBJECT_STORAGE_BUCKET, Key=object_key)
            return response["Body"].read()

        minio_module = importlib.import_module("minio")
        Minio = getattr(minio_module, "Minio")
        endpoint = OBJECT_STORAGE_ENDPOINT.replace("https://", "").replace("http://", "")
        minio_client = Minio(
            endpoint,
            access_key=OBJECT_STORAGE_ACCESS_KEY,
            secret_key=OBJECT_STORAGE_SECRET_KEY,
            secure=OBJECT_STORAGE_ENDPOINT.startswith("https://"),
        )
        response = minio_client.get_object(OBJECT_STORAGE_BUCKET, object_key)
        try:
            return response.read()
        finally:
            close = getattr(response, "close", None)
            release_conn = getattr(response, "release_conn", None)
            if close:
                close()
            if release_conn:
                release_conn()
    except Exception:
        return b""


def store_attachment_asset(file_bytes: bytes, mime_type: str) -> tuple[str, bool, int, str, str]:
    digest = hashlib.sha256(file_bytes).hexdigest()
    compressed, payload = compress_bytes(file_bytes)
    object_backend, object_key = upload_object_storage(f"attachments/{digest}", payload, mime_type)
    assets = st.session_state.data.setdefault("attachments", {})
    if digest not in assets:
        stored_in_database = not object_backend
        assets[digest] = {
            "hash": digest,
            "mime_type": mime_type,
            "size": len(file_bytes),
            "stored_size": len(payload) if stored_in_database else 0,
            "object_size": len(payload) if object_backend else 0,
            "compressed": compressed,
            "payload": base64.b64encode(payload).decode("ascii") if stored_in_database else "",
            "created_at": current_stamp(),
            "ref_count": 0,
            "storage_backend": object_backend or "local",
            "object_key": object_key,
        }
    assets[digest]["ref_count"] = safe_int(assets[digest].get("ref_count"), 0) + 1
    asset = assets[digest]
    return (
        digest,
        bool(asset.get("compressed")),
        safe_int(asset.get("stored_size"), len(file_bytes)),
        asset.get("storage_backend", "local"),
        asset.get("object_key", ""),
    )


def attachment_data_uri(attachment: dict[str, Any]) -> str:
    if attachment.get("data_uri"):
        return attachment.get("data_uri", "")
    asset_hash = attachment.get("asset_hash", "")
    asset = st.session_state.data.get("attachments", {}).get(asset_hash)
    if not asset:
        return ""
    try:
        if asset.get("payload"):
            payload = base64.b64decode(asset.get("payload", ""))
        else:
            payload = download_object_storage(asset)
            if not payload:
                return ""
        if asset.get("compressed"):
            payload = zlib.decompress(payload)
        encoded = base64.b64encode(payload).decode("ascii")
        mime_type = attachment.get("mime_type") or asset.get("mime_type") or "application/octet-stream"
        return f"data:{mime_type};base64,{encoded}"
    except (binascii.Error, ValueError, zlib.error):
        return ""


def group_role(group: dict[str, Any], username: str) -> str:
    if username == group.get("admin"):
        return "owner"
    return group.get("roles", {}).get(username, "member")


def can_manage_group(group: dict[str, Any], username: str) -> bool:
    return group_role(group, username) in {"owner", "admin"}


def can_change_group_roles(group: dict[str, Any], username: str) -> bool:
    return group_role(group, username) == "owner"


def can_send_to_group(group: dict[str, Any], username: str) -> bool:
    return username in group.get("members", []) and group_role(group, username) != "muted"


def set_group_role(group_id: str, target: str, role: str, actor: str) -> tuple[bool, str]:
    group = get_group(group_id)
    if not group:
        return False, "Group not found."
    if not can_change_group_roles(group, actor):
        return False, "Only the group owner can change roles."
    if target == group.get("admin"):
        return False, "Owner role cannot be changed."
    if target not in group.get("members", []):
        return False, "User is not in this group."
    if role not in {"admin", "member", "muted"}:
        return False, "Choose a valid role."
    group.setdefault("roles", {})[target] = role
    save_data(st.session_state.data)
    return True, f"@{target} is now {role}."


def conversation_search_score(current_user: str, item: dict[str, Any], query: str) -> int:
    needle = query.strip().lower()
    if not needle:
        return 1
    score = 0
    title = item["title"].lower()
    subtitle = item["subtitle"].lower()
    if title == needle:
        score += 120
    elif needle in title:
        score += 70
    elif fuzzy_ratio(needle, title) >= 0.72:
        score += 45
    if needle in subtitle:
        score += 25
    latest = latest_message(current_user, item["conversation_id"]).lower()
    if latest == needle:
        score += 90
    elif needle in latest:
        score += 45
    elif fuzzy_ratio(needle, latest[:120]) >= 0.72:
        score += 28
    query_words = text_words(needle)
    for message in st.session_state.data["messages"].get(item["conversation_id"], []):
        text = message_text(item["conversation_id"], message).lower()
        sender = get_user(message.get("sender", ""))
        sender_label = " ".join(
            [
                message.get("sender", ""),
                sender.get("display_name", "") if sender else "",
                sender.get("email", "") if sender else "",
            ]
        ).lower()
        if needle in sender_label:
            score += 35
        elif fuzzy_ratio(needle, sender_label) >= 0.74:
            score += 24
        if needle in text:
            score += 20 + min(40, text.count(needle) * 8)
        elif fuzzy_ratio(needle, text[:160]) >= 0.72:
            score += 16
        if query_words:
            message_words = Counter(text_words(text))
            score += min(30, sum(message_words.get(word, 0) for word in query_words) * 3)
        for attachment in message.get("attachments", []):
            if needle in attachment.get("name", "").lower():
                score += 25
            elif fuzzy_ratio(needle, attachment.get("name", "")) >= 0.75:
                score += 14
    if score:
        score += min(25, count_unread(current_user, item["conversation_id"]) * 3)
    return score


def ranked_chat_items(current_user: str, items: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    if not query.strip():
        return items
    scored = [
        (conversation_search_score(current_user, item, query), timestamp_sort_value(latest_message_stamp(item["conversation_id"])), item)
        for item in items
    ]
    return [item for score, _, item in sorted(scored, key=lambda value: (-value[0], -value[1])) if score > 0]


def message_search_score(conversation_id: str, message: dict[str, Any], query: str) -> int:
    needle = query.strip().lower()
    if not needle:
        return 1
    text = message_text(conversation_id, message).lower()
    sender = get_user(message.get("sender", ""))
    sender_label = " ".join(
        [
            message.get("sender", ""),
            sender.get("display_name", "") if sender else "",
            sender.get("email", "") if sender else "",
        ]
    ).lower()
    score = 0
    if text == needle:
        score += 120
    elif needle in text:
        score += 55 + min(50, text.count(needle) * 10)
    elif fuzzy_ratio(needle, text[:160]) >= 0.72:
        score += 35
    if needle in sender_label:
        score += 40
    elif fuzzy_ratio(needle, sender_label) >= 0.74:
        score += 24
    query_words = text_words(needle)
    if query_words:
        message_words = Counter(text_words(text))
        score += min(35, sum(message_words.get(word, 0) for word in query_words) * 4)
    for attachment in message.get("attachments", []):
        if needle in attachment.get("name", "").lower():
            score += 25
        elif fuzzy_ratio(needle, attachment.get("name", "")) >= 0.75:
            score += 14
    return score


def shared_group_ids(first_user: str, second_user: str) -> set[str]:
    return {
        group_id
        for group_id, group in st.session_state.data.get("groups", {}).items()
        if first_user in group.get("members", []) and second_user in group.get("members", [])
    }


def friend_recommendations(username: str, limit: int = 3) -> list[dict[str, Any]]:
    user = get_user(username)
    if not user:
        return []
    friends = set(user.get("friends", []))
    blocked = set(user.get("blocked_users", []))
    recommendations = []
    for candidate_name, candidate in st.session_state.data["users"].items():
        if candidate_name == username or candidate_name in friends or candidate_name in blocked:
            continue
        if pending_request_between(username, candidate_name):
            continue
        candidate_friends = set(candidate.get("friends", []))
        mutual = sorted(friends & candidate_friends)
        common_groups = shared_group_ids(username, candidate_name)
        recent_score = 1 if parse_stamp(candidate.get("last_seen_at")) else 0
        score = len(mutual) * 3 + len(common_groups) * 2 + recent_score
        if score:
            recommendations.append(
                {
                    "user": candidate,
                    "score": score,
                    "reason": f"{len(mutual)} mutual friend(s), {len(common_groups)} common group(s)",
                }
            )
    return sorted(recommendations, key=lambda item: (-item["score"], item["user"]["display_name"].lower()))[:limit]


def group_recommendations(username: str, limit: int = 3) -> list[dict[str, Any]]:
    user = get_user(username)
    friends = set(user.get("friends", [])) if user else set()
    recommendations = []
    for group in st.session_state.data.get("groups", {}).values():
        members = set(group.get("members", []))
        if username in members:
            continue
        friend_count = len(friends & members)
        if friend_count:
            recommendations.append(
                {
                    "group": group,
                    "score": friend_count * 2 + len(members),
                    "reason": f"{friend_count} friend(s) already in this group",
                }
            )
    return sorted(recommendations, key=lambda item: (-item["score"], item["group"]["name"].lower()))[:limit]


def important_unread_count(username: str) -> int:
    user = get_user(username)
    if not user:
        return 0
    important = 0
    for item in chat_items(username, show_archived=True):
        conversation_id = item["conversation_id"]
        unread_messages = [
            message
            for message in st.session_state.data["messages"].get(conversation_id, [])
            if message.get("sender") != username and username not in message.get("read_by", []) and not message.get("deleted")
        ]
        if not unread_messages:
            continue
        for message in unread_messages:
            if notification_priority_score(username, conversation_id, message) >= 50:
                important += 1
    return important


def notification_priority_score(username: str, conversation_id: str, message: dict[str, Any]) -> int:
    user = get_user(username)
    text = message_text(conversation_id, message).lower()
    score = 10
    if user and is_pinned(user, conversation_id):
        score += 35
    if f"@{username}".lower() in text:
        score += 40
    score += min(25, count_unread(username, conversation_id) * 5)
    score += 20 if any(keyword in text for keyword in IMPORTANT_KEYWORDS) else 0
    custom_keywords = [keyword.lower() for keyword in (user or {}).get("notification_keywords", [])]
    score += 20 if any(keyword and keyword in text for keyword in custom_keywords) else 0
    return min(100, score)


def create_backup(label: str = "Manual backup") -> tuple[bool, str]:
    snapshot = json.loads(json.dumps(st.session_state.data))
    snapshot["backups"] = []
    payload = json.dumps(snapshot, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(payload, level=6)
    backup = {
        "id": str(uuid.uuid4()),
        "label": label.strip() or "Manual backup",
        "created_at": current_stamp(),
        "schema_version": snapshot.get("schema_version", 4),
        "size": len(payload),
        "stored_size": len(compressed),
        "checksum": hashlib.sha256(payload).hexdigest(),
        "payload": base64.b64encode(compressed).decode("ascii"),
    }
    backups = st.session_state.data.setdefault("backups", [])
    backups.insert(0, backup)
    del backups[BACKUP_RETENTION_LIMIT:]
    save_data(st.session_state.data)
    return True, "Backup created."


def backup_display_label(backup: dict[str, Any]) -> str:
    stored_kb = safe_int(backup.get("stored_size"), 0) // 1024
    label = backup.get("label", "Backup")
    created_at = backup.get("created_at", "")
    return f"{created_at} | {label} | {stored_kb} KB"


def restore_backup(backup_id: str) -> tuple[bool, str]:
    backup = next((item for item in st.session_state.data.get("backups", []) if item.get("id") == backup_id), None)
    if not backup:
        return False, "Backup not found."
    try:
        payload_bytes = zlib.decompress(base64.b64decode(backup.get("payload", "")))
        checksum = backup.get("checksum", "")
        if checksum and hashlib.sha256(payload_bytes).hexdigest() != checksum:
            return False, "Backup checksum verification failed."
        payload = payload_bytes.decode("utf-8")
        restored = ensure_data_shape(json.loads(payload))
    except (binascii.Error, ValueError, zlib.error, UnicodeDecodeError, json.JSONDecodeError):
        return False, "Backup could not be restored."
    restored["backups"] = st.session_state.data.get("backups", [])
    current_user = st.session_state.get("current_user")
    st.session_state.data = restored
    if current_user not in restored.get("users", {}):
        st.session_state.current_user = None
        st.session_state.active_friend = None
        st.session_state.active_group = None
    save_data(st.session_state.data)
    return True, "Backup restored."


def rotate_encryption_keys() -> tuple[bool, str]:
    if not crypto_available():
        return False, "Install cryptography to rotate encryption keys."
    current_user = st.session_state.get("current_user", "")
    if not current_user or not current_private_key(current_user):
        return False, "Encryption key is locked. Log in again to rotate keys."
    old_version = active_encryption_version()
    new_version = old_version + 1
    rotated = 0
    for conversation_id, messages in st.session_state.data.get("messages", {}).items():
        members = conversation_members(conversation_id)
        if current_user not in members or members_missing_public_keys(conversation_id):
            continue
        readable_messages = []
        for message in messages:
            if message.get("deleted"):
                continue
            plaintext = message_text(conversation_id, message)
            if plaintext in MESSAGE_TEXT_FAILURES:
                continue
            readable_messages.append((message, plaintext))
        if not readable_messages:
            continue
        fresh_cipher, fresh_key_id = create_fresh_conversation_cipher(conversation_id)
        if not fresh_cipher:
            continue
        for message, plaintext in readable_messages:
            message.pop("text", None)
            message.pop("text_payload", None)
            message.pop("ciphertext", None)
            message.update(encrypted_payload_with_cipher(plaintext, new_version, fresh_cipher, fresh_key_id))
            rotated += 1
    encryption = st.session_state.data.setdefault("encryption", {})
    encryption["active_key_version"] = new_version
    encryption.setdefault("rotations", []).append(
        {"from": old_version, "to": new_version, "created_at": current_stamp(), "messages": rotated}
    )
    save_data(st.session_state.data)
    return True, f"Rotated encryption to v{new_version} for {rotated} message(s)."


def summarize_conversation(current_user: str, conversation_id: str, unread_only: bool = False) -> str:
    messages = []
    for message in st.session_state.data["messages"].get(conversation_id, []):
        if message.get("deleted"):
            continue
        if unread_only and (message.get("sender") == current_user or current_user in message.get("read_by", [])):
            continue
        messages.append(message)
    if not messages:
        return "No messages to summarize."
    selected = messages[-40:]
    sender_counts = Counter(message.get("sender", "") for message in selected)
    attachment_count = sum(len(message.get("attachments", [])) for message in selected)
    words = Counter(
        word
        for message in selected
        for word in text_words(message_text(conversation_id, message))
        if len(word) > 3 and word not in SUMMARY_STOP_WORDS
    )
    top_senders = []
    for sender, count in sender_counts.most_common(3):
        user = get_user(sender)
        top_senders.append(f"{user['display_name'] if user else sender} ({count})")
    topics = ", ".join(word for word, _ in words.most_common(5)) or "general chat"
    latest = selected[-1]
    latest_sender = get_user(latest.get("sender", ""))
    latest_name = latest_sender["display_name"] if latest_sender else latest.get("sender", "Someone")
    return (
        f"{len(selected)} message(s) summarized. Latest from {latest_name} at {latest.get('time', '')}. "
        f"Top senders: {', '.join(top_senders)}. Topics: {topics}. Attachments: {attachment_count}."
    )


def message_option_label(conversation_id: str, message: dict[str, Any]) -> str:
    text = message_text(conversation_id, message)
    attachment_label = "attachment" if message.get("attachments") else ""
    preview = text or attachment_label or "message"
    return f"{message.get('time', '')} - {preview[:48]}"


def username_for_email(email_value: str) -> str | None:
    email = normalize_email(email_value)
    for username, user in st.session_state.data["users"].items():
        if normalize_email(user.get("email", "")) == email:
            return username
    return None


def email_is_available(email_value: str, current_username: str | None = None) -> bool:
    email = normalize_email(email_value)
    for username, user in st.session_state.data["users"].items():
        if username == current_username:
            continue
        if normalize_email(user.get("email", "")) == email:
            return False
    return True


def username_for_friend_identifier(value: str) -> str | None:
    identifier = value.strip()
    if EMAIL_PATTERN.fullmatch(identifier.lower()):
        return username_for_email(identifier)
    username = normalize_username(identifier)
    if username in st.session_state.data["users"]:
        return username
    return None


def avatar_html(user: dict[str, Any], class_name: str = "avatar") -> str:
    photo_data_uri = user.get("photo_data_uri", "")
    if photo_data_uri:
        return (
            f'<img class="{class_name} avatar-img" '
            f'src="{escape(photo_data_uri)}" '
            f'alt="{escape(user["display_name"])} profile photo">'
        )
    return (
        f'<div class="{class_name}" style="background:{escape(user.get("accent", "#04986d"))}">'
        f'{escape(initials(user.get("display_name", "User")))}'
        "</div>"
    )


def group_avatar_html(group: dict[str, Any], class_name: str = "avatar") -> str:
    photo_data_uri = group.get("photo_data_uri", "")
    if photo_data_uri:
        return (
            f'<img class="{class_name} avatar-img" '
            f'src="{escape(photo_data_uri)}" '
            f'alt="{escape(group["name"])} group photo">'
        )
    return (
        f'<div class="{class_name}" style="background:{escape(group.get("accent", "#2f80ed"))}">'
        f'{escape(initials(group.get("name", "Group")))}'
        "</div>"
    )


def profile_contact_line(user: dict[str, Any]) -> str:
    parts = [f'@{user["username"]}', user.get("status", "available")]
    email = user.get("email", "")
    phone_number = user.get("phone_number", "")
    if email:
        parts.append(email)
    if phone_number:
        parts.append(f'{user.get("country_code", "")} {phone_number}'.strip())
    return " | ".join(parts)


def uploaded_photo_to_data_uri(uploaded_photo: Any) -> tuple[bool, str]:
    if not uploaded_photo:
        return True, ""

    mime_type = getattr(uploaded_photo, "type", "")
    if mime_type not in PHOTO_TYPES:
        return False, "Upload a JPG, PNG, or WebP image."

    photo_bytes = uploaded_photo.getvalue()
    if len(photo_bytes) > 1_500_000:
        return False, "Profile photo must be under 1.5 MB."

    encoded = base64.b64encode(photo_bytes).decode("ascii")
    return True, f"data:{mime_type};base64,{encoded}"


def uploaded_file_to_attachment(uploaded_file: Any) -> tuple[bool, dict[str, Any] | str]:
    file_bytes = uploaded_file.getvalue()
    if len(file_bytes) > MAX_ATTACHMENT_BYTES:
        return False, f"{uploaded_file.name} is too large. Limit is {MAX_ATTACHMENT_BYTES // 1_000_000} MB."
    mime_type = getattr(uploaded_file, "type", "") or "application/octet-stream"
    scan_status, scan_issues = scan_attachment_bytes(file_bytes, uploaded_file.name, mime_type)
    if scan_status == "blocked":
        return False, f"{uploaded_file.name} blocked by media scan: {', '.join(scan_issues)}."
    asset_hash, compressed, stored_size, storage_backend, object_key = store_attachment_asset(file_bytes, mime_type)
    category = "file"
    if mime_type.startswith("image/"):
        category = "image"
    elif mime_type.startswith("audio/"):
        category = "audio"
    elif mime_type.startswith("video/"):
        category = "video"
    return True, {
        "id": str(uuid.uuid4()),
        "name": uploaded_file.name,
        "mime_type": mime_type,
        "size": len(file_bytes),
        "stored_size": stored_size,
        "asset_hash": asset_hash,
        "compressed": compressed,
        "scan_status": scan_status,
        "scan_issues": scan_issues,
        "thumbnail_data_uri": thumbnail_for_attachment(file_bytes, mime_type),
        "storage_backend": storage_backend,
        "object_bucket": OBJECT_STORAGE_BUCKET,
        "object_key": object_key,
        "category": category,
    }


def update_profile(
    username: str,
    display_name: str,
    email: str,
    selected_country_label: str,
    phone_number: str,
    status: str,
    theme: str,
    accent_color: str,
    uploaded_photo: Any,
    clear_photo: bool,
) -> tuple[bool, str]:
    user = get_user(username)
    if not user:
        return False, "User not found."

    cleaned_name = display_name.strip()
    cleaned_email = email.strip().lower()
    cleaned_phone = phone_number.strip()
    cleaned_status = status.strip() or "available"

    if not cleaned_name:
        return False, "Display name is required."
    if not cleaned_email:
        return False, "Mail ID is required."
    if not EMAIL_PATTERN.fullmatch(cleaned_email):
        return False, "Enter a valid email address."
    if not email_is_available(cleaned_email, username):
        return False, "That mail ID is already used by another account."
    if cleaned_phone and not PHONE_PATTERN.fullmatch(cleaned_phone):
        return False, "Enter a valid contact number."

    country_option = next(
        (option for option in COUNTRY_CODE_OPTIONS if option["label"] == selected_country_label),
        COUNTRY_CODE_OPTIONS[0],
    )
    user["display_name"] = cleaned_name
    user["email"] = cleaned_email
    user["country_code"] = country_option["code"]
    user["country_region"] = country_option["region"]
    user["phone_number"] = cleaned_phone
    user["status"] = cleaned_status
    user["theme"] = theme if theme in THEMES else "Light"
    user["accent_color"] = accent_color if accent_color in ACCENTS else "#04986d"

    if clear_photo:
        user["photo_data_uri"] = ""
    elif uploaded_photo:
        success, result = uploaded_photo_to_data_uri(uploaded_photo)
        if not success:
            return False, result
        user["photo_data_uri"] = result

    save_data(st.session_state.data)
    return True, "Profile updated."


def sorted_friend_users(username: str) -> list[dict[str, Any]]:
    user = get_user(username)
    if not user:
        return []
    friends = [get_user(friend) for friend in user["friends"]]
    return sorted((friend for friend in friends if friend), key=lambda item: item["display_name"].lower())


def are_friends(first_user: str, second_user: str) -> bool:
    first = get_user(first_user)
    second = get_user(second_user)
    return bool(first and second and second_user in first["friends"] and first_user in second["friends"])


def blocked_between(first_user: str, second_user: str) -> bool:
    first = get_user(first_user)
    second = get_user(second_user)
    return bool(
        first
        and second
        and (second_user in first.get("blocked_users", []) or first_user in second.get("blocked_users", []))
    )


def pending_request_between(first_user: str, second_user: str) -> dict[str, Any] | None:
    for request in st.session_state.data["friend_requests"]:
        users = {request["from"], request["to"]}
        if users == {first_user, second_user}:
            return request
    return None


def incoming_requests(username: str) -> list[dict[str, Any]]:
    return [request for request in st.session_state.data["friend_requests"] if request["to"] == username]


def outgoing_requests(username: str) -> list[dict[str, Any]]:
    return [request for request in st.session_state.data["friend_requests"] if request["from"] == username]


def add_friendship(first_user: str, second_user: str) -> None:
    first = get_user(first_user)
    second = get_user(second_user)
    if not first or not second:
        return
    first["friends"] = sorted(set(first["friends"]) | {second_user})
    second["friends"] = sorted(set(second["friends"]) | {first_user})


def remove_request(request_id: str) -> None:
    st.session_state.data["friend_requests"] = [
        request for request in st.session_state.data["friend_requests"] if request["id"] != request_id
    ]


def send_friend_request(sender: str, target_value: str) -> tuple[bool, str]:
    target = username_for_friend_identifier(target_value)
    if not target:
        return False, "Enter a valid username or mail ID."
    if target == sender:
        return False, "You cannot add yourself."
    if blocked_between(sender, target):
        return False, "You cannot send a request to this user."
    if are_friends(sender, target):
        return False, "You are already friends."

    existing = pending_request_between(sender, target)
    if existing:
        if existing["to"] == sender:
            add_friendship(sender, target)
            remove_request(existing["id"])
            save_data(st.session_state.data)
            return True, f"You and @{target} are now friends."
        return False, "A request is already pending."

    allowed, rate_message = check_rate_limit(sender, "friend_request")
    if not allowed:
        return False, rate_message
    st.session_state.data["friend_requests"].append(
        {
            "id": str(uuid.uuid4()),
            "from": sender,
            "to": target,
            "created_at": current_stamp(),
        }
    )
    save_data(st.session_state.data)
    return True, f"Request sent to @{target}."


def respond_to_request(request_id: str, accept: bool) -> None:
    request = next((item for item in st.session_state.data["friend_requests"] if item["id"] == request_id), None)
    if not request:
        return
    if accept:
        add_friendship(request["from"], request["to"])
        st.session_state.active_friend = request["from"]
        st.session_state.active_group = None
    remove_request(request_id)
    save_data(st.session_state.data)


def create_group(current_user: str, group_name: str, member_names: list[str], uploaded_photo: Any) -> tuple[bool, str]:
    cleaned_name = group_name.strip()
    if not cleaned_name:
        return False, "Group name is required."
    members = sorted(set(member_names + [current_user]))
    if len(members) < 2:
        return False, "Choose at least one friend."

    group_id = uuid.uuid4().hex[:12]
    photo_data_uri = ""
    if uploaded_photo:
        success, result = uploaded_photo_to_data_uri(uploaded_photo)
        if not success:
            return False, result
        photo_data_uri = result
    st.session_state.data["groups"][group_id] = {
        "id": group_id,
        "name": cleaned_name,
        "admin": current_user,
        "members": members,
        "roles": {member: ("owner" if member == current_user else "member") for member in members},
        "photo_data_uri": photo_data_uri,
        "accent": ACCENTS[len(st.session_state.data["groups"]) % len(ACCENTS)],
        "created_at": current_stamp(),
        "invite_code": uuid.uuid4().hex[:10],
        "approval_required": False,
        "join_requests": [],
    }
    save_data(st.session_state.data)
    st.session_state.active_group = group_id
    st.session_state.active_friend = None
    return True, "Group created."


def update_group_members(group_id: str, add_members: list[str], remove_members: list[str]) -> None:
    group = get_group(group_id)
    if not group:
        return
    members = set(group["members"])
    members.update(add_members)
    members.difference_update(remove_members)
    members.add(group["admin"])
    group["members"] = sorted(members)
    roles = group.setdefault("roles", {})
    for member in add_members:
        roles.setdefault(member, "member")
    for member in remove_members:
        if member != group.get("admin"):
            roles.pop(member, None)
    roles[group["admin"]] = "owner"
    save_data(st.session_state.data)


def leave_group(group_id: str, username: str) -> None:
    group = get_group(group_id)
    if not group:
        return
    remaining_members = sorted(member for member in group["members"] if member != username)
    if not remaining_members:
        st.session_state.data["groups"].pop(group_id, None)
        st.session_state.data["messages"].pop(group_chat_id(group_id), None)
        save_data(st.session_state.data)
        st.session_state.active_group = None
        return
    if username == group.get("admin") and len(group["members"]) > 1:
        group["admin"] = remaining_members[0]
        group.setdefault("roles", {})[group["admin"]] = "owner"
    group["members"] = remaining_members
    group.setdefault("roles", {}).pop(username, None)
    save_data(st.session_state.data)
    st.session_state.active_group = None


def conversation_members(conversation_id: str) -> list[str]:
    return conversation_members_from_data(st.session_state.data, conversation_id)


def latest_message(current_user: str, conversation_id: str) -> str:
    messages = st.session_state.data["messages"].get(conversation_id, [])
    if not messages:
        return "No messages yet"
    message = messages[-1]
    text = message_text(conversation_id, message)
    attachments = message.get("attachments", [])
    if attachments and not text:
        text = f"{len(attachments)} attachment(s)"
    if is_group_conversation(conversation_id) and message.get("sender") != current_user:
        sender = get_user(message.get("sender", ""))
        if sender:
            return f"{sender['display_name']}: {text}"
    return text


def latest_message_stamp(conversation_id: str) -> str:
    messages = st.session_state.data["messages"].get(conversation_id, [])
    if messages:
        return messages[-1].get("created_at", "")
    if is_group_conversation(conversation_id):
        group = get_group(conversation_id.removeprefix(GROUP_PREFIX))
        return group.get("created_at", "") if group else ""
    return ""


def count_unread(username: str, conversation_id: str) -> int:
    return sum(
        1
        for message in st.session_state.data["messages"].get(conversation_id, [])
        if message.get("sender") != username and username not in message.get("read_by", []) and not message.get("deleted")
    )


def total_unread(username: str) -> int:
    return sum(count_unread(username, item["conversation_id"]) for item in chat_items(username, show_archived=True))


def mark_conversation_read(username: str, conversation_id: str) -> None:
    changed = False
    for message in st.session_state.data["messages"].get(conversation_id, []):
        if message.get("sender") == username:
            continue
        if username not in message.get("delivered_to", []):
            message["delivered_to"] = sorted(set(message.get("delivered_to", [])) | {username})
            changed = True
        if username in message.get("read_by", []):
            continue
        message["read_by"] = sorted(set(message.get("read_by", [])) | {username})
        message["state"] = message_state_from_lists(message, conversation_members(conversation_id))
        changed = True
    if changed:
        save_data(st.session_state.data)
        notify_realtime_event(conversation_id, "read", username)


def mark_conversation_delivered(username: str, conversation_id: str) -> None:
    changed = False
    for message in st.session_state.data["messages"].get(conversation_id, []):
        if message.get("sender") == username or username in message.get("delivered_to", []):
            continue
        message["delivered_to"] = sorted(set(message.get("delivered_to", [])) | {username})
        message["state"] = message_state_from_lists(message, conversation_members(conversation_id))
        changed = True
    if changed:
        save_data(st.session_state.data)
        notify_realtime_event(conversation_id, "delivered", username)


def is_pinned(user: dict[str, Any], conversation_id: str) -> bool:
    return conversation_id in user.get("pinned_chats", [])


def is_archived(user: dict[str, Any], conversation_id: str) -> bool:
    return conversation_id in user.get("archived_chats", [])


def toggle_list_value(values: list[str], value: str) -> list[str]:
    values_set = set(values)
    if value in values_set:
        values_set.remove(value)
    else:
        values_set.add(value)
    return sorted(values_set)


def toggle_pin(username: str, conversation_id: str) -> None:
    user = get_user(username)
    if user:
        user["pinned_chats"] = toggle_list_value(user.get("pinned_chats", []), conversation_id)
        save_data(st.session_state.data)


def toggle_archive(username: str, conversation_id: str) -> None:
    user = get_user(username)
    if user:
        user["archived_chats"] = toggle_list_value(user.get("archived_chats", []), conversation_id)
        save_data(st.session_state.data)


def add_message_to_conversation(
    sender: str,
    conversation_id: str,
    text: str,
    attachments: list[dict[str, Any]] | None = None,
    reply_to: str = "",
    forwarded_from: str = "",
    expires_at: str = "",
    poll: dict[str, Any] | None = None,
    skip_rate_limit: bool = False,
) -> tuple[bool, str]:
    cleaned = text.strip()
    attachments = attachments or []
    if not cleaned and not attachments and not poll:
        return False, "Type a message or attach a file."
    members = conversation_members(conversation_id)
    if not is_group_conversation(conversation_id):
        other_members = [member for member in members if member != sender]
        if other_members and blocked_between(sender, other_members[0]):
            return False, "Messaging is blocked for this chat."
    else:
        group = get_group(conversation_id.removeprefix(GROUP_PREFIX))
        if not group or not can_send_to_group(group, sender):
            return False, "You are muted or not allowed to send messages in this group."
    if sender not in members:
        return False, "You are not a member of this chat."
    if crypto_available():
        if not current_private_key(sender):
            return False, "Encryption key is locked. Log in again to unlock secure messaging."
        missing_keys = members_missing_public_keys(conversation_id)
        if missing_keys:
            missing_label = ", ".join(f"@{member}" for member in missing_keys[:4])
            return False, f"Secure messaging is waiting for encryption keys from {missing_label}. Ask them to log in once."

    if not skip_rate_limit:
        allowed, rate_message = check_rate_limit(f"{sender}:{conversation_id}", "message")
        if not allowed:
            return False, rate_message

    content_issues = detect_content_issues(cleaned)
    spam_score = spam_detection_score(sender, conversation_id, cleaned, attachments)
    toxic_score = toxicity_score(cleaned)
    blocking_issues = [issue["label"] for issue in content_issues if issue["severity"] == "block"]
    if spam_score >= 70:
        blocking_issues.append("Repeated message spam")
    if blocking_issues:
        return False, f"Message blocked: {', '.join(blocking_issues)}."

    moderation_flags = [issue["label"] for issue in content_issues]
    if spam_score >= 35:
        moderation_flags.append(f"Spam score {spam_score}")
    if toxic_score >= 50:
        moderation_flags.append(f"Toxicity score {toxic_score}")
    update_user_reputation(sender, spam_score, moderation_flags)
    recipients = [member for member in members if member != sender]
    message_id = str(uuid.uuid4())
    message = {
        "id": message_id,
        "sender": sender,
        "time": current_time(),
        "created_at": current_stamp(),
        "edited_at": "",
        "deleted": False,
        "deleted_at": "",
        "expires_at": expires_at,
        "reply_to": reply_to,
        "forwarded_from": forwarded_from,
        "attachments": attachments,
        "read_by": [sender],
        "delivered_to": [],
        "state": "sent",
        "moderation_flags": moderation_flags,
        "spam_score": spam_score,
        "toxicity_score": toxic_score,
        "topic_labels": topic_labels_for_text(cleaned),
        "duplicate_cluster_id": duplicate_cluster_id(conversation_id, sender, cleaned),
        "reactions": {},
        "starred_by": [],
        "poll": poll,
        "conflict_version": 1,
        **encrypted_message_payload(conversation_id, cleaned),
    }
    st.session_state.data["messages"].setdefault(conversation_id, []).append(message)
    if moderation_flags:
        st.session_state.data.setdefault("moderation_queue", []).append(
            {
                "id": str(uuid.uuid4()),
                "conversation_id": conversation_id,
                "message_id": message_id,
                "sender": sender,
                "flags": moderation_flags,
                "created_at": current_stamp(),
                "status": "open",
            }
        )
    for member in recipients:
        send_push_notification(member, "New ChatLite message", latest_message(member, conversation_id), conversation_id)
        member_user = get_user(member)
        online_until = parse_stamp(member_user.get("online_until")) if member_user else None
        if not online_until or online_until <= datetime.now():
            st.session_state.data.setdefault("offline_queue", {}).setdefault(member, []).append(
                {
                    "id": str(uuid.uuid4()),
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "created_at": current_stamp(),
                    "retry_count": 0,
                    "status": "queued",
                }
            )
    clear_typing(sender, conversation_id)
    save_data(st.session_state.data)
    notify_realtime_event(conversation_id, "message", sender, message_id)
    return True, "Message sent."


def edit_message(conversation_id: str, message_id: str, new_text: str, editor: str) -> tuple[bool, str]:
    cleaned = new_text.strip()
    if not cleaned:
        return False, "Message text cannot be empty."
    if crypto_available() and not current_private_key(editor):
        return False, "Encryption key is locked. Log in again to edit secure messages."
    content_issues = detect_content_issues(cleaned)
    blocking_issues = [issue["label"] for issue in content_issues if issue["severity"] == "block"]
    if blocking_issues:
        return False, f"Edit blocked: {', '.join(blocking_issues)}."
    for message in st.session_state.data["messages"].get(conversation_id, []):
        if message["id"] == message_id and message.get("sender") == editor and not message.get("deleted"):
            message.pop("text", None)
            message.pop("text_payload", None)
            message.pop("ciphertext", None)
            message.update(encrypted_message_payload(conversation_id, cleaned))
            message["edited_at"] = current_stamp()
            message["state"] = "edited"
            message["conflict_version"] = safe_int(message.get("conflict_version"), 1) + 1
            message["topic_labels"] = topic_labels_for_text(cleaned)
            message["moderation_flags"] = [issue["label"] for issue in content_issues]
            save_data(st.session_state.data)
            notify_realtime_event(conversation_id, "edit", editor, message_id)
            return True, "Message edited."
    return False, "Message not found."


def delete_message(conversation_id: str, message_id: str, editor: str) -> tuple[bool, str]:
    for message in st.session_state.data["messages"].get(conversation_id, []):
        if message["id"] == message_id and message.get("sender") == editor and not message.get("deleted"):
            message["deleted"] = True
            message["deleted_at"] = current_stamp()
            message["attachments"] = []
            message["state"] = "deleted"
            message["conflict_version"] = safe_int(message.get("conflict_version"), 1) + 1
            message.pop("text", None)
            message.pop("text_payload", None)
            message.pop("ciphertext", None)
            save_data(st.session_state.data)
            notify_realtime_event(conversation_id, "delete", editor, message_id)
            return True, "Message deleted."
    return False, "Message not found."


def receipt_html(conversation_id: str, message: dict[str, Any], current_user: str) -> str:
    if message.get("sender") != current_user:
        return ""
    state = message.get("state") or message_state_from_lists(message, conversation_members(conversation_id))
    others = [member for member in conversation_members(conversation_id) if member != current_user]
    read_count = sum(1 for member in others if member in message.get("read_by", []))
    delivered_count = sum(1 for member in others if member in message.get("delivered_to", []))
    if state == "read" or (others and read_count == len(others)):
        return '<span class="receipt receipt-read" title="read">&#10003;&#10003;</span>'
    if delivered_count:
        return f'<span class="receipt" title="{escape(state)}">&#10003;&#10003;</span>'
    return f'<span class="receipt" title="{escape(state)}">&#10003;</span>'


def record_typing(username: str, conversation_id: str, draft: str) -> None:
    typing = st.session_state.data.setdefault("typing", {}).setdefault(conversation_id, {})
    changed = False
    if draft.strip():
        now = datetime.now()
        previous = parse_stamp(typing.get(username))
        if not previous or (now - previous).total_seconds() >= TYPING_DEBOUNCE_SECONDS:
            typing[username] = now.isoformat(timespec="seconds")
            changed = True
    elif username in typing:
        typing.pop(username, None)
        changed = True
    if changed:
        save_data(st.session_state.data)


def clear_typing(username: str, conversation_id: str) -> None:
    typing = st.session_state.data.setdefault("typing", {}).setdefault(conversation_id, {})
    if username in typing:
        typing.pop(username, None)


def typing_label(current_user: str, conversation_id: str) -> str:
    active_names = []
    now = datetime.now()
    for username, stamp in st.session_state.data.get("typing", {}).get(conversation_id, {}).items():
        if username == current_user:
            continue
        typed_at = parse_stamp(stamp)
        if typed_at and now - typed_at <= timedelta(seconds=12):
            user = get_user(username)
            active_names.append(user["display_name"] if user else username)
    if not active_names:
        return ""
    if len(active_names) == 1:
        return f"{active_names[0]} is typing..."
    return "Several people are typing..."


def touch_presence(username: str) -> None:
    user = get_user(username)
    if not user:
        return
    now = datetime.now()
    user["last_seen_at"] = now.isoformat(timespec="seconds")
    user["online_until"] = (now + timedelta(minutes=2)).isoformat(timespec="seconds")
    touch_device_session(username)
    save_data(st.session_state.data)


def set_offline(username: str) -> None:
    user = get_user(username)
    if not user:
        return
    user["last_seen_at"] = current_stamp()
    user["online_until"] = datetime.now().isoformat(timespec="seconds")
    save_data(st.session_state.data)


def presence_label(user: dict[str, Any]) -> str:
    online_until = parse_stamp(user.get("online_until"))
    if online_until and online_until > datetime.now():
        return "online"
    last_seen = parse_stamp(user.get("last_seen_at"))
    if not last_seen:
        return "offline"
    if last_seen.date() == datetime.now().date():
        return f"last seen today at {last_seen.strftime('%H:%M')}"
    return f"last seen {last_seen.strftime('%b %d at %H:%M')}"


def request_password_reset(email_value: str) -> tuple[bool, str]:
    email = normalize_email(email_value)
    if not EMAIL_PATTERN.fullmatch(email):
        return False, "Enter a valid mail ID."
    allowed, rate_message = check_rate_limit(email, "password_reset")
    if not allowed:
        return False, rate_message
    username = username_for_email(email)
    user = get_user(username) if username else None
    if not user:
        return False, "No account found for this mail ID."
    code = f"{random.randint(100000, 999999)}"
    user["password_reset"] = {
        "code_hash": password_hash(username, code),
        "expires_at": (datetime.now() + timedelta(minutes=15)).isoformat(timespec="seconds"),
    }
    save_data(st.session_state.data)
    try:
        if send_reset_email(email, code):
            st.session_state.reset_code_preview = ""
            return True, "Reset code sent to your mail ID."
    except (OSError, smtplib.SMTPException) as exc:
        st.session_state.reset_code_preview = code
        return True, f"SMTP failed, demo reset code generated instead: {exc}"
    st.session_state.reset_code_preview = code
    return True, "Demo reset code generated. Configure SMTP to send real email."


def complete_password_reset(email_value: str, code: str, new_password: str, confirm_password: str) -> tuple[bool, str]:
    email = normalize_email(email_value)
    if not EMAIL_PATTERN.fullmatch(email):
        return False, "Enter a valid mail ID."
    allowed, rate_message = check_rate_limit(f"{email}:complete", "password_reset")
    if not allowed:
        return False, rate_message
    username = username_for_email(email)
    user = get_user(username) if username else None
    if not user:
        return False, "No account found for this mail ID."
    reset = user.get("password_reset", {})
    expires_at = parse_stamp(reset.get("expires_at"))
    if not reset or not expires_at or expires_at < datetime.now():
        return False, "Reset code expired. Generate a new code."
    if not hmac.compare_digest(password_hash(username, code.strip()), reset.get("code_hash", "")):
        return False, "Invalid reset code."
    if len(new_password) < 4:
        return False, "Password must be at least 4 characters."
    if new_password != confirm_password:
        return False, "Passwords do not match."
    user["password_hash"] = password_hash(username, new_password)
    reset_user_encryption_identity(username, new_password)
    user["password_reset"] = {}
    clear_rate_limit(email, "password_reset")
    clear_rate_limit(f"{email}:complete", "password_reset")
    save_data(st.session_state.data)
    return True, "Password reset. You can log in now."


def create_account(
    email_value: str,
    username_value: str,
    display_name: str,
    password: str,
    confirm_password: str,
) -> tuple[bool, str]:
    email = normalize_email(email_value)
    username = normalize_username(username_value)
    if not EMAIL_PATTERN.fullmatch(email):
        return False, "Enter a valid mail ID."
    if not email_is_available(email):
        return False, "That mail ID already has an account."
    if not is_valid_username(username):
        return False, "Use 3-20 lowercase letters, numbers, or underscores."
    if username in st.session_state.data["users"]:
        return False, "That username is already taken."
    if len(password) < 4:
        return False, "Password must be at least 4 characters."
    if password != confirm_password:
        return False, "Passwords do not match."

    st.session_state.data["users"][username] = make_user(username, display_name, password, email)
    save_data(st.session_state.data)
    st.session_state.current_user = username
    unlock_user_private_key(username, password)
    st.session_state.current_session_id = create_device_session(username)
    st.session_state.active_friend = None
    st.session_state.active_group = None
    touch_presence(username)
    return True, "Account created."


def login(email_value: str, password: str) -> tuple[bool, str]:
    email = normalize_email(email_value)
    allowed, rate_message = check_rate_limit(email, "login")
    if not allowed:
        return False, rate_message
    username = username_for_email(email)
    user = get_user(username) if username else None
    if not user or not verify_password(username, password, user.get("password_hash", "")):
        return False, "Invalid mail ID or password."

    clear_rate_limit(email, "login")
    if crypto_available() and not unlock_user_private_key(username, password):
        return False, "Encryption key could not be unlocked for this account."
    anomaly_flags = detect_login_anomaly(user)
    st.session_state.current_user = username
    st.session_state.current_session_id = create_device_session(username)
    st.session_state.active_friend = None
    st.session_state.active_group = None
    user["last_login_at"] = current_stamp()
    user["last_login_ip"] = os.getenv("CHATLITE_CLIENT_IP", user.get("last_login_ip", ""))
    if anomaly_flags:
        send_push_notification(username, "Security alert", ", ".join(anomaly_flags))
    touch_presence(username)
    return True, "Logged in."


def logout() -> None:
    current_user = st.session_state.get("current_user")
    if current_user:
        logout_device(current_user, st.session_state.get("current_session_id", ""))
        set_offline(current_user)
    st.session_state.current_user = None
    st.session_state.current_session_id = None
    st.session_state.active_friend = None
    st.session_state.active_group = None
    st.query_params.clear()


def block_user(current_user: str, target: str) -> None:
    user = get_user(current_user)
    if not user:
        return
    user["blocked_users"] = sorted(set(user.get("blocked_users", [])) | {target})
    save_data(st.session_state.data)


def unblock_user(current_user: str, target: str) -> None:
    user = get_user(current_user)
    if not user:
        return
    user["blocked_users"] = sorted(value for value in user.get("blocked_users", []) if value != target)
    save_data(st.session_state.data)


def report_user(current_user: str, target: str, reason: str) -> tuple[bool, str]:
    cleaned = reason.strip()
    if not cleaned:
        return False, "Add a short reason."
    user = get_user(current_user)
    if user:
        user["reported_users"] = sorted(set(user.get("reported_users", [])) | {target})
    st.session_state.data["reports"].append(
        {
            "id": str(uuid.uuid4()),
            "from": current_user,
            "target": target,
            "reason": cleaned,
            "created_at": current_stamp(),
        }
    )
    save_data(st.session_state.data)
    return True, "Report saved."


def chat_items(username: str, show_archived: bool = False) -> list[dict[str, Any]]:
    user = get_user(username)
    if not user:
        return []
    items: list[dict[str, Any]] = []
    for friend in sorted_friend_users(username):
        conversation_id = private_chat_id(username, friend["username"])
        if is_archived(user, conversation_id) and not show_archived:
            continue
        items.append(
            {
                "kind": "private",
                "conversation_id": conversation_id,
                "title": friend["display_name"],
                "subtitle": presence_label(friend),
                "href": f"?chat={escape(friend['username'])}",
                "avatar": avatar_html(friend),
                "friend_username": friend["username"],
            }
        )
    for group in st.session_state.data["groups"].values():
        if username not in group.get("members", []):
            continue
        conversation_id = group_chat_id(group["id"])
        if is_archived(user, conversation_id) and not show_archived:
            continue
        items.append(
            {
                "kind": "group",
                "conversation_id": conversation_id,
                "title": group["name"],
                "subtitle": f"{len(group['members'])} members",
                "href": f"?group={escape(group['id'])}",
                "avatar": group_avatar_html(group),
                "group_id": group["id"],
            }
        )

    def online_score(item: dict[str, Any]) -> int:
        if item["kind"] == "private":
            friend = get_user(item.get("friend_username", ""))
            online_until = parse_stamp(friend.get("online_until")) if friend else None
            return 1 if online_until and online_until > datetime.now() else 0
        group_id = item.get("group_id", "")
        group = get_group(group_id) if group_id else None
        if not group:
            return 0
        score = 0
        for member in group.get("members", []):
            if member == username:
                continue
            member_user = get_user(member)
            online_until = parse_stamp(member_user.get("online_until")) if member_user else None
            if online_until and online_until > datetime.now():
                score += 1
        return score

    def sort_key(item: dict[str, Any]) -> tuple[int, int, float, int, str]:
        pinned = 0 if is_pinned(user, item["conversation_id"]) else 1
        unread_first = -count_unread(username, item["conversation_id"])
        newest_first = -timestamp_sort_value(latest_message_stamp(item["conversation_id"]))
        online_first = -online_score(item)
        return (pinned, unread_first, newest_first, online_first, item["title"].lower())

    return sorted(items, key=sort_key)


def conversation_matches_query(current_user: str, item: dict[str, Any], query: str) -> bool:
    if not query.strip():
        return True
    return conversation_search_score(current_user, item, query) > 0


def total_attachments_html(message: dict[str, Any]) -> str:
    parts = []
    for attachment in message.get("attachments", []):
        name = escape(attachment.get("name", "attachment"))
        data_uri = escape(attachment_data_uri(attachment))
        mime_type = escape(attachment.get("mime_type", ""))
        category = attachment.get("category", "file")
        if not data_uri:
            parts.append(f'<div class="attachment-file">{name} unavailable</div>')
            continue
        if category == "image":
            parts.append(f'<img class="attachment-image" src="{data_uri}" alt="{name}">')
        elif category == "audio":
            parts.append(f'<audio class="attachment-player" controls src="{data_uri}"></audio>')
        elif category == "video":
            parts.append(f'<video class="attachment-video" controls src="{data_uri}"></video>')
        else:
            parts.append(
                f'<a class="attachment-file" href="{data_uri}" download="{name}" type="{mime_type}">{name}</a>'
            )
    return "".join(parts)


def reactions_html(message: dict[str, Any]) -> str:
    reactions = message.get("reactions", {})
    if not reactions:
        return ""
    parts = [
        f'<span class="reaction-chip">{escape(reaction)} {len(users)}</span>'
        for reaction, users in reactions.items()
        if users
    ]
    return f'<div class="reaction-row">{"".join(parts)}</div>' if parts else ""


def poll_html(message: dict[str, Any]) -> str:
    poll = message.get("poll")
    if not poll:
        return ""
    total_votes = sum(len(option.get("votes", [])) for option in poll.get("options", [])) or 1
    options_html = []
    for option in poll.get("options", []):
        votes = len(option.get("votes", []))
        percent = round(votes * 100 / total_votes)
        options_html.append(
            '<div class="poll-option">'
            f'<div>{escape(option.get("text", ""))}</div>'
            f'<div class="poll-bar"><span style="width:{percent}%"></span></div>'
            f'<small>{votes} vote(s)</small>'
            '</div>'
        )
    return f'<div class="poll-card"><b>{escape(poll.get("question", "Poll"))}</b>{"".join(options_html)}</div>'


def reply_html(conversation_id: str, message: dict[str, Any]) -> str:
    reply_to = message.get("reply_to")
    if not reply_to:
        return ""
    original = find_message(conversation_id, reply_to)
    return f'<div class="reply-preview">{escape(message_preview(conversation_id, original, 96))}</div>'


def message_labels_html(message: dict[str, Any]) -> str:
    labels = []
    if message.get("forwarded_from"):
        labels.append("forwarded")
    if message.get("expires_at"):
        labels.append("disappearing")
    labels.extend(label for label in message.get("topic_labels", []) if label != "general")
    if not labels:
        return ""
    return f'<div class="topic-labels">{"".join(f"<span>{escape(label)}</span>" for label in labels[:4])}</div>'


def theme_override_css() -> str:
    current_user = st.session_state.get("current_user")
    user = get_user(current_user) if current_user else None
    accent = user.get("accent_color", "#04986d") if user else "#04986d"
    dark = user and user.get("theme") == "Dark"
    dark_css = ""
    if dark:
        dark_css = """
        .stApp {
            background:
                linear-gradient(180deg, rgba(4, 120, 87, 0.96) 0 104px, transparent 104px),
                linear-gradient(135deg, #101820 0%, #151f28 52%, #0d141b 100%);
        }
        [data-testid="stSidebar"] {
            background: #111a22;
            color: #e8edf2;
            border-color: #263440;
        }
        .sidebar-top,
        .profile-summary,
        .profile-grid,
        .contact-card.active,
        .contact-card:hover,
        .request-card,
        .empty-side,
        .search-wrap,
        .st-key-chat-shell,
        .chat-header,
        div[class*="st-key-composer-"],
        .tool-panel {
            background: #17212b !important;
            border-color: #263440 !important;
            color: #e8edf2 !important;
        }
        .chat-wall {
            background-color: #0f171f !important;
            background-image: radial-gradient(circle at 22px 18px, rgba(255, 255, 255, 0.045) 0 1.3px, transparent 1.4px) !important;
        }
        .message-row.them .message-bubble {
            background: #202b35 !important;
            color: #f2f6fa;
        }
        .contact-name,
        .header-name,
        .profile-name {
            color: #f4f7fa !important;
        }
        .contact-preview,
        .header-status,
        .request-meta,
        .message-time,
        .profile-contact {
            color: #a6b1bc !important;
        }
        .stTextInput input,
        .stTextArea textarea,
        .stSelectbox [data-baseweb="select"] {
            background: #101820 !important;
            color: #f4f7fa !important;
            border-color: #263440 !important;
        }
        """
    return f"""
    <style>
    :root {{
        --wa-green: {accent};
        --wa-green-dark: {accent};
    }}
    {dark_css}
    </style>
    """


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --wa-green: #04986d;
            --wa-green-dark: #027a61;
            --wa-bg: #f5f0e8;
            --wa-panel: #ffffff;
            --wa-panel-soft: #f7f9fb;
            --wa-text: #17212b;
            --wa-muted: #65727f;
            --wa-line: #e3e9ee;
            --wa-bubble-me: #dcf8d7;
            --wa-bubble-them: #ffffff;
            --danger: #b42318;
            --shadow-soft: 0 18px 48px rgba(23, 33, 43, 0.13);
            --shadow-low: 0 8px 24px rgba(23, 33, 43, 0.08);
        }

        .stApp {
            background:
                linear-gradient(180deg, rgba(4, 152, 109, 0.96) 0 104px, transparent 104px),
                linear-gradient(135deg, #edf7f2 0%, #f7f5ef 44%, #eef3f7 100%);
            color: var(--wa-text);
        }

        header[data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        footer {
            display: none !important;
        }

        .block-container {
            max-width: 1240px;
            min-height: 100vh;
            padding: 26px 22px 22px;
        }

        [data-testid="stSidebar"] {
            background: #fbfcfd;
            border-right: 1px solid rgba(117, 132, 148, 0.18);
            box-shadow: 10px 0 28px rgba(23, 33, 43, 0.06);
        }

        [data-testid="stSidebar"] > div:first-child {
            padding: 0 0 14px;
        }

        .auth-panel {
            max-width: 440px;
            margin: 70px auto 18px;
            background: #ffffff;
            border-radius: 8px;
            border: 1px solid rgba(227, 233, 238, 0.9);
            box-shadow: var(--shadow-soft);
            padding: 28px;
        }

        .auth-mark {
            width: 42px;
            height: 42px;
            border-radius: 8px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: var(--wa-green);
            color: #ffffff;
            font-weight: 900;
            margin-bottom: 14px;
        }

        .auth-title {
            font-size: 30px;
            line-height: 1.1;
            font-weight: 800;
            letter-spacing: 0;
            color: var(--wa-text);
            margin-bottom: 6px;
        }

        .auth-subtitle,
        .contact-preview,
        .header-status,
        .request-meta,
        .message-time,
        .profile-contact {
            color: var(--wa-muted);
            font-size: 13px;
        }

        .sidebar-top {
            background: linear-gradient(135deg, #ffffff 0%, #eef8f4 100%);
            padding: 18px;
            border-bottom: 1px solid var(--wa-line);
        }

        .brand-row,
        .chat-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
        }

        .brand-title {
            font-size: 23px;
            font-weight: 800;
            letter-spacing: 0;
            color: var(--wa-text);
        }

        .status-dot {
            width: 9px;
            height: 9px;
            display: inline-block;
            border-radius: 50%;
            background: var(--wa-green);
            margin-right: 6px;
            box-shadow: 0 0 0 3px rgba(4, 152, 109, 0.13);
        }

        .contact-card {
            display: grid;
            grid-template-columns: 44px minmax(0, 1fr) auto;
            gap: 12px;
            align-items: center;
            margin: 6px 10px;
            padding: 11px 12px;
            border: 1px solid transparent;
            border-radius: 8px;
            color: var(--wa-text);
            text-decoration: none;
            transition: background 140ms ease, border-color 140ms ease, box-shadow 140ms ease;
        }

        .contact-card.active,
        .contact-card:hover {
            background: #ffffff;
            border-color: var(--wa-line);
            box-shadow: var(--shadow-low);
        }

        div[class*="st-key-open_"] {
            margin: -4px 10px 6px;
        }

        div[class*="st-key-open_"] button {
            min-height: 30px;
            font-size: 12px;
            background: transparent;
            box-shadow: none;
        }

        .contact-link,
        .contact-link:hover,
        .contact-link:visited,
        .contact-link:active {
            color: inherit;
            text-decoration: none;
        }

        .avatar,
        .mini-avatar {
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: #ffffff;
            font-weight: 800;
            box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.28);
            flex: 0 0 auto;
        }

        .avatar {
            width: 44px;
            height: 44px;
            font-size: 14px;
        }

        .mini-avatar {
            width: 34px;
            height: 34px;
            font-size: 12px;
            margin-right: 8px;
            vertical-align: middle;
        }

        .avatar-img {
            object-fit: cover;
            padding: 0;
            background: #d9dee3;
        }

        .contact-name,
        .header-name,
        .profile-name {
            font-weight: 800;
            color: var(--wa-text);
            overflow-wrap: anywhere;
        }

        .contact-preview {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .contact-meta {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 6px;
        }

        .unread-badge,
        .pin-badge,
        .archive-badge,
        .notify-badge {
            border-radius: 999px;
            font-size: 11px;
            font-weight: 800;
            padding: 3px 8px;
            white-space: nowrap;
        }

        .unread-badge,
        .notify-badge {
            background: var(--wa-green);
            color: #ffffff;
        }

        .pin-badge {
            background: #fff7df;
            color: #9a6700;
            border: 1px solid #ffe3a3;
        }

        .archive-badge {
            background: #eef2f7;
            color: #50606f;
            border: 1px solid var(--wa-line);
        }

        .section-title {
            padding: 16px 16px 5px;
            color: #50606f;
            font-size: 11px;
            font-weight: 900;
            letter-spacing: 0;
            text-transform: uppercase;
        }

        .empty-side,
        .request-card,
        .tool-panel {
            margin: 8px 10px 6px;
            padding: 12px;
            border: 1px solid var(--wa-line);
            border-radius: 8px;
            background: #ffffff;
        }

        .empty-side {
            border-style: dashed;
            color: var(--wa-muted);
            font-size: 13px;
        }

        .profile-summary {
            display: flex;
            align-items: center;
            gap: 12px;
            background: #ffffff;
            border: 1px solid var(--wa-line);
            border-radius: 8px;
            padding: 12px;
            margin-top: 8px;
        }

        .profile-grid {
            display: grid;
            grid-template-columns: 78px minmax(0, 1fr);
            gap: 6px 10px;
            background: #f7f9fb;
            border: 1px solid var(--wa-line);
            border-radius: 8px;
            padding: 10px 12px;
            margin: 8px 0 12px;
            font-size: 12px;
        }

        .profile-grid span:nth-child(odd) {
            color: var(--wa-muted);
            font-weight: 800;
        }

        .profile-grid span:nth-child(even) {
            overflow-wrap: anywhere;
        }

        .search-wrap {
            margin: 10px;
            padding: 0;
            border: 1px solid var(--wa-line);
            border-radius: 8px;
            background: #ffffff;
        }

        .st-key-chat-shell {
            overflow: hidden;
            border-radius: 8px;
            border: 1px solid rgba(227, 233, 238, 0.95);
            background: #ffffff;
            box-shadow: var(--shadow-soft);
        }

        .st-key-chat-shell > div[data-testid="stVerticalBlock"] {
            gap: 0;
        }

        .chat-header {
            background: linear-gradient(180deg, #ffffff 0%, #f7f9fb 100%);
            padding: 16px 20px;
            border-bottom: 1px solid var(--wa-line);
            border-radius: 8px 8px 0 0;
        }

        .header-left {
            display: flex;
            align-items: center;
            gap: 14px;
            min-width: 0;
        }

        .header-name {
            font-size: 17px;
        }

        .security-pill,
        .typing-pill {
            display: inline-flex;
            align-items: center;
            width: fit-content;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 800;
            padding: 4px 9px;
            margin-top: 5px;
        }

        .security-pill {
            background: #e8f8ef;
            color: #047857;
            border: 1px solid #bfe8d0;
        }

        .typing-pill {
            background: #eef6ff;
            color: #1d4ed8;
            border: 1px solid #bfdcff;
        }

        .header-actions {
            display: flex;
            gap: 10px;
        }

        .toolbar-btn {
            min-width: 34px;
            height: 34px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: var(--wa-muted);
            border: 1px solid var(--wa-line);
            background: #ffffff;
            box-shadow: 0 2px 8px rgba(23, 33, 43, 0.05);
            font-weight: 800;
        }

        .chat-wall {
            min-height: calc(100vh - 318px);
            max-height: calc(100vh - 318px);
            overflow-y: auto;
            background-color: #f6f1e8;
            background-image:
                linear-gradient(rgba(255, 255, 255, 0.58), rgba(255, 255, 255, 0.58)),
                radial-gradient(circle at 22px 18px, rgba(23, 33, 43, 0.045) 0 1.3px, transparent 1.4px);
            background-size: auto, 44px 44px;
            padding: 26px 30px;
        }

        .message-row {
            display: flex;
            margin: 8px 0;
        }

        .message-row.me {
            justify-content: flex-end;
        }

        .message-row.them {
            justify-content: flex-start;
        }

        .message-bubble {
            max-width: min(74%, 620px);
            padding: 9px 11px 7px;
            border-radius: 8px;
            color: var(--wa-text);
            box-shadow: 0 2px 9px rgba(23, 33, 43, 0.09);
            overflow-wrap: anywhere;
            line-height: 1.38;
            font-size: 15px;
        }

        .message-row.me .message-bubble {
            background: linear-gradient(180deg, #e3ffd9 0%, #d9fdd3 100%);
            border-top-right-radius: 2px;
        }

        .message-row.them .message-bubble {
            background: #ffffff;
            border-top-left-radius: 2px;
        }

        .message-sender {
            color: var(--wa-green-dark);
            font-size: 12px;
            font-weight: 900;
            margin-bottom: 3px;
        }

        .message-meta {
            display: flex;
            justify-content: flex-end;
            align-items: center;
            gap: 5px;
            margin-top: 2px;
            color: var(--wa-muted);
            font-size: 11px;
        }

        .receipt-read {
            color: #2f80ed;
            font-weight: 900;
        }

        .deleted-message,
        .edited-label {
            color: var(--wa-muted);
            font-style: italic;
        }

        .moderation-flag {
            margin-top: 6px;
            padding: 5px 7px;
            border-radius: 8px;
            background: #fff7df;
            border: 1px solid #ffe3a3;
            color: #7a4c00;
            font-size: 11px;
            font-weight: 800;
        }

        .reply-preview,
        .poll-card {
            margin-bottom: 7px;
            padding: 7px 8px;
            border-left: 3px solid var(--wa-green);
            border-radius: 8px;
            background: rgba(4, 152, 109, 0.08);
            color: #50606f;
            font-size: 12px;
            font-weight: 800;
        }

        .reaction-row,
        .topic-labels {
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin-top: 6px;
        }

        .reaction-chip,
        .topic-labels span {
            border-radius: 999px;
            padding: 3px 7px;
            background: rgba(80, 96, 111, 0.1);
            color: #50606f;
            font-size: 11px;
            font-weight: 800;
        }

        .poll-option {
            margin-top: 8px;
        }

        .poll-bar {
            height: 6px;
            border-radius: 999px;
            background: rgba(80, 96, 111, 0.16);
            overflow: hidden;
            margin: 4px 0;
        }

        .poll-bar span {
            display: block;
            height: 100%;
            background: var(--wa-green);
        }

        .attachment-image,
        .attachment-video {
            display: block;
            max-width: min(100%, 360px);
            border-radius: 8px;
            margin-top: 8px;
        }

        .attachment-player {
            width: min(100%, 320px);
            margin-top: 8px;
        }

        .attachment-file {
            display: block;
            margin-top: 8px;
            padding: 9px 10px;
            border-radius: 8px;
            border: 1px solid rgba(80, 96, 111, 0.18);
            background: rgba(255, 255, 255, 0.56);
            color: var(--wa-text);
            text-decoration: none;
            font-weight: 800;
        }

        div[class*="st-key-composer-"] {
            padding: 14px 18px 16px;
            background: #f7f9fb;
            border-top: 1px solid var(--wa-line);
            border-radius: 0 0 8px 8px;
        }

        div[class*="st-key-composer-"] > div[data-testid="stVerticalBlock"] {
            gap: 8px;
        }

        div[class*="st-key-composer-"] [data-testid="column"] {
            display: flex;
            align-items: stretch;
        }

        div[class*="st-key-composer-"] [data-testid="column"] > div {
            width: 100%;
        }

        .stTextInput input,
        .stTextArea textarea {
            border-radius: 8px;
            border: 1px solid var(--wa-line);
            background: #ffffff;
            min-height: 42px;
        }

        .search-wrap .stTextInput input {
            border: 0;
            background: transparent;
        }

        .stTextInput input:focus,
        .stTextArea textarea:focus {
            border-color: rgba(4, 152, 109, 0.72);
            box-shadow: 0 0 0 3px rgba(4, 152, 109, 0.12);
        }

        .stButton > button,
        .stFormSubmitButton > button {
            border-radius: 8px;
            border-color: var(--wa-line);
            background: #ffffff;
            color: var(--wa-text);
            font-weight: 800;
            min-height: 38px;
        }

        .stButton > button:hover {
            border-color: rgba(4, 152, 109, 0.45);
            color: var(--wa-green-dark);
        }

        .stFormSubmitButton > button,
        .stButton > button[kind="primary"] {
            background: linear-gradient(180deg, var(--wa-green) 0%, var(--wa-green-dark) 100%);
            color: #ffffff;
            border-color: var(--wa-green-dark);
            box-shadow: 0 6px 16px rgba(2, 122, 97, 0.22);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background: #f7f9fb;
            padding: 5px;
            border: 1px solid var(--wa-line);
            border-radius: 8px;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 8px;
            min-height: 40px;
        }

        .stTabs [aria-selected="true"] {
            background: #ffffff;
            box-shadow: var(--shadow-low);
        }

        .empty-state {
            min-height: calc(100vh - 318px);
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(255, 255, 255, 0.34);
            color: #66727f;
            text-align: center;
            padding: 36px;
            font-weight: 800;
        }

        @media (max-width: 760px) {
            .block-container {
                padding: 0;
            }

            .auth-panel {
                margin: 0 0 14px;
                min-height: auto;
                border-radius: 0;
                box-shadow: none;
            }

            .st-key-chat-shell {
                border-radius: 0;
                box-shadow: none;
                border-left: 0;
                border-right: 0;
            }

            .chat-wall {
                min-height: calc(100vh - 330px);
                max-height: calc(100vh - 330px);
                padding: 18px 12px;
            }

            .message-bubble {
                max-width: 88%;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(theme_override_css(), unsafe_allow_html=True)


def render_auth_screen() -> None:
    _, auth_col, _ = st.columns([1, 1.05, 1])
    with auth_col:
        st.markdown(
            """
            <div class="auth-panel">
                <div class="auth-mark">CL</div>
                <div class="auth-title">ChatLite</div>
                <div class="auth-subtitle">Log in with your mail ID to continue.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        login_tab, create_tab, reset_tab = st.tabs(["Log in", "Create account", "Reset password"])

        with login_tab:
            with st.form("login_form"):
                email = st.text_input("Mail ID", placeholder="demo@chatlite.local", key="login_email")
                password = st.text_input("Password", type="password", placeholder="demo123", key="login_password")
                submitted = st.form_submit_button("Log in", use_container_width=True)
            if submitted:
                success, message = login(email, password)
                if success:
                    st.rerun()
                st.error(message)

        with create_tab:
            with st.form("create_account_form"):
                new_email = st.text_input("Mail ID", placeholder="you@example.com", key="create_email")
                new_username = st.text_input("Username", placeholder="your_name", key="create_username")
                display_name = st.text_input("Display name", placeholder="Your Name", key="create_display_name")
                new_password = st.text_input("Create password", type="password", key="create_password")
                confirm_password = st.text_input("Confirm password", type="password", key="create_confirm_password")
                created = st.form_submit_button("Create account", use_container_width=True)
            if created:
                success, message = create_account(new_email, new_username, display_name, new_password, confirm_password)
                if success:
                    st.success(message)
                    st.rerun()
                st.error(message)

        with reset_tab:
            with st.form("reset_request_form"):
                reset_email = st.text_input("Mail ID", placeholder="you@example.com", key="reset_request_email")
                requested = st.form_submit_button("Generate reset code", use_container_width=True)
            if requested:
                success, message = request_password_reset(reset_email)
                if success:
                    st.success(message)
                    st.info(f"Demo reset code: {st.session_state.reset_code_preview}")
                else:
                    st.error(message)

            with st.form("reset_complete_form"):
                reset_email_confirm = st.text_input("Mail ID", placeholder="you@example.com", key="reset_email_confirm")
                reset_code = st.text_input("Reset code", key="reset_code")
                new_password = st.text_input("New password", type="password", key="reset_new_password")
                confirm_new_password = st.text_input("Confirm new password", type="password", key="reset_confirm_password")
                reset_done = st.form_submit_button("Reset password", use_container_width=True)
            if reset_done:
                success, message = complete_password_reset(
                    reset_email_confirm,
                    reset_code,
                    new_password,
                    confirm_new_password,
                )
                if success:
                    st.success(message)
                else:
                    st.error(message)


def render_profile_editor(current_user: str) -> None:
    user = get_user(current_user)
    if not user:
        return

    with st.expander("Profile", expanded=False):
        st.markdown(
            f"""
            <div class="profile-summary">
                {avatar_html(user)}
                <div>
                    <div class="profile-name">{escape(user['display_name'])}</div>
                    <div class="profile-contact">{escape(profile_contact_line(user))}</div>
                </div>
            </div>
            <div class="profile-grid">
                <span>Mail ID</span><span>{escape(user.get('email', ''))}</span>
                <span>Username</span><span>@{escape(user['username'])}</span>
                <span>Contact</span><span>{escape((user.get('country_code', '') + ' ' + user.get('phone_number', '')).strip() or 'Not added')}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        labels = [option["label"] for option in COUNTRY_CODE_OPTIONS]
        with st.form("profile_form"):
            display_name = st.text_input("Display name", value=user["display_name"], key=f"profile_name_{current_user}")
            email = st.text_input(
                "Mail ID",
                value=user.get("email", ""),
                placeholder="name@example.com",
                key=f"profile_email_{current_user}",
            )
            selected_country = st.selectbox(
                "Country code",
                labels,
                index=country_option_index(user),
                key=f"profile_country_{current_user}",
            )
            phone_number = st.text_input(
                "Contact number",
                value=user.get("phone_number", ""),
                placeholder="9876543210",
                key=f"profile_phone_{current_user}",
            )
            status = st.text_input("Status", value=user.get("status", "available"), key=f"profile_status_{current_user}")
            theme = st.selectbox(
                "Theme",
                THEMES,
                index=THEMES.index(user.get("theme", "Light")) if user.get("theme") in THEMES else 0,
                key=f"profile_theme_{current_user}",
            )
            accent_color = st.selectbox(
                "Accent color",
                ACCENTS,
                index=ACCENTS.index(user.get("accent_color", "#04986d"))
                if user.get("accent_color") in ACCENTS
                else 0,
                key=f"profile_accent_{current_user}",
            )
            uploaded_photo = file_uploader_compat(
                "Profile photo",
                file_types=["jpg", "jpeg", "png", "webp"],
                accept_multiple_files=False,
                max_upload_size=2,
                key=f"profile_photo_{current_user}",
            )
            clear_photo = st.checkbox("Remove current photo", key=f"profile_clear_photo_{current_user}")
            submitted = st.form_submit_button("Save profile", use_container_width=True)

        if submitted:
            success, message = update_profile(
                current_user,
                display_name,
                email,
                selected_country,
                phone_number,
                status,
                theme,
                accent_color,
                uploaded_photo,
                clear_photo,
            )
            if success:
                st.success(message)
                st.rerun()
            else:
                st.warning(message)


def render_chat_item(current_user: str, item: dict[str, Any]) -> str:
    user = get_user(current_user)
    conversation_id = item["conversation_id"]
    unread = count_unread(current_user, conversation_id)
    active_id = active_conversation_id(current_user)
    active = " active" if conversation_id == active_id else ""
    meta = []
    if user and is_pinned(user, conversation_id):
        meta.append('<span class="pin-badge">Pinned</span>')
    if user and is_archived(user, conversation_id):
        meta.append('<span class="archive-badge">Archived</span>')
    if unread:
        meta.append(f'<span class="unread-badge">{unread}</span>')
    meta_html = "".join(meta)
    return f"""
        <div class="contact-card{active}">
            {item['avatar']}
            <div style="min-width:0">
                <div class="contact-name">{escape(item['title'])}</div>
                <div class="contact-preview">{escape(latest_message(current_user, conversation_id))}</div>
            </div>
            <div class="contact-meta">{meta_html}</div>
        </div>
    """


def open_chat_item(item: dict[str, Any]) -> None:
    if item["kind"] == "group":
        st.session_state.active_group = item.get("group_id")
        st.session_state.active_friend = None
    else:
        st.session_state.active_friend = item.get("friend_username")
        st.session_state.active_group = None
    st.query_params.clear()


def render_request_card(request: dict[str, Any], current_user: str) -> None:
    requester = get_user(request["from"])
    if not requester:
        return
    st.markdown(
        f"""
        <div class="request-card">
            <div>
                {avatar_html(requester, "mini-avatar")}
                <span class="contact-name">{escape(requester['display_name'])}</span>
            </div>
            <div class="request-meta">@{escape(requester['username'])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    accept_col, decline_col = st.columns(2)
    with accept_col:
        if st.button("Accept", key=f"accept-{request['id']}"):
            respond_to_request(request["id"], accept=True)
            st.rerun()
    with decline_col:
        if st.button("Decline", key=f"decline-{request['id']}"):
            respond_to_request(request["id"], accept=False)
            st.rerun()


def render_group_creator(current_user: str) -> None:
    friends = sorted_friend_users(current_user)
    friend_names = [friend["username"] for friend in friends]
    with st.expander("Create group", expanded=False):
        with st.form("create_group_form"):
            group_name = st.text_input("Group name", placeholder="Friends, Project, Family")
            selected = st.multiselect(
                "Members",
                friend_names,
                format_func=lambda name: get_user(name)["display_name"] if get_user(name) else name,
            )
            group_photo = file_uploader_compat(
                "Group photo",
                file_types=["jpg", "jpeg", "png", "webp"],
                accept_multiple_files=False,
                max_upload_size=2,
                key=f"group_photo_{current_user}",
            )
            submitted = st.form_submit_button("Create group", use_container_width=True)
        if submitted:
            success, message = create_group(current_user, group_name, selected, group_photo)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.warning(message)


def render_security_backup_tools(current_user: str) -> None:
    with st.expander("Security & backups", expanded=False):
        assets = st.session_state.data.get("attachments", {})
        saved_bytes = sum(
            max(0, safe_int(asset.get("size"), 0) - safe_int(asset.get("stored_size"), 0))
            for asset in assets.values()
        )
        st.caption(
            f"{active_storage_backend().upper()} storage | {len(assets)} unique attachment(s) | "
            f"{saved_bytes // 1024} KB saved"
        )
        rotations = st.session_state.data.get("encryption", {}).get("rotations", [])
        if rotations:
            latest_rotation = rotations[-1]
            st.caption(
                f"Key audit: v{latest_rotation.get('from')} -> v{latest_rotation.get('to')} | "
                f"{latest_rotation.get('messages', 0)} message(s) | {latest_rotation.get('created_at', '')}"
            )
        if st.button("Rotate encryption keys", key=f"rotate_keys_{current_user}", use_container_width=True):
            success, message = rotate_encryption_keys()
            if success:
                st.success(message)
                st.rerun()
            else:
                st.warning(message)

        backup_label = st.text_input("Backup label", value="Manual backup", key=f"backup_label_{current_user}")
        if st.button("Create backup", key=f"create_backup_{current_user}", use_container_width=True):
            success, message = create_backup(backup_label)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.warning(message)

        backups = st.session_state.data.get("backups", [])
        if backups:
            backup_by_id = {backup["id"]: backup for backup in backups if backup.get("id")}
            if backup_by_id:
                selected_backup_id = st.selectbox(
                    "Restore point",
                    list(backup_by_id),
                    format_func=lambda backup_id: backup_display_label(backup_by_id[backup_id]),
                    key=f"restore_select_{current_user}",
                )
                selected_backup = backup_by_id[selected_backup_id]
                if st.button("Restore selected backup", key=f"restore_backup_{current_user}", use_container_width=True):
                    success, message = restore_backup(selected_backup["id"])
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.warning(message)
            else:
                st.caption("Saved backups are missing restore IDs.")
        else:
            st.caption("No backups yet.")


def render_recommendations(current_user: str) -> None:
    friend_recs = friend_recommendations(current_user)
    group_recs = group_recommendations(current_user)
    if not friend_recs and not group_recs:
        return

    st.markdown('<div class="section-title">Recommendations</div>', unsafe_allow_html=True)
    for recommendation in friend_recs:
        suggested = recommendation["user"]
        st.markdown(
            f"""
            <div class="request-card">
                <div>
                    {avatar_html(suggested, "mini-avatar")}
                    <span class="contact-name">{escape(suggested['display_name'])}</span>
                </div>
                <div class="request-meta">@{escape(suggested['username'])} | {escape(recommendation['reason'])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            f"Request @{suggested['username']}",
            key=f"recommend_friend_{suggested['username']}",
            use_container_width=True,
        ):
            success, message = send_friend_request(current_user, suggested["username"])
            if success:
                st.success(message)
                st.rerun()
            else:
                st.warning(message)

    for recommendation in group_recs:
        group = recommendation["group"]
        st.markdown(
            f"""
            <div class="request-card">
                <div>
                    {group_avatar_html(group, "mini-avatar")}
                    <span class="contact-name">{escape(group['name'])}</span>
                </div>
                <div class="request-meta">{escape(recommendation['reason'])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_contact_and_invite_tools(current_user: str) -> None:
    with st.expander("Contacts & invites", expanded=False):
        raw_contacts = st.text_area(
            "Import contacts",
            placeholder="Paste mail IDs, usernames, or phone numbers",
            key=f"contact_import_{current_user}",
        )
        if st.button("Import contacts", key=f"import_contacts_{current_user}", use_container_width=True):
            sent, messages = import_contacts(current_user, raw_contacts)
            st.success(f"{sent} request(s) sent.")
            if messages:
                st.caption(" | ".join(messages[:6]))

        invite_code = st.text_input("Group invite code", key=f"join_invite_{current_user}")
        if st.button("Join group", key=f"join_group_invite_{current_user}", use_container_width=True):
            success, message = request_group_join(invite_code, current_user)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.warning(message)


def render_user_activity_dashboard(current_user: str) -> None:
    with st.expander("Activity", expanded=False):
        stats = user_activity_stats(current_user)
        st.markdown(
            f"""
            <div class="profile-grid">
                <span>Messages</span><span>{stats['messages_sent']}</span>
                <span>Starred</span><span>{stats['starred']}</span>
                <span>Calls</span><span>{stats['calls']}</span>
                <span>Scheduled</span><span>{stats['scheduled']}</span>
                <span>Trust</span><span>{user_trust_score(current_user)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        user = get_user(current_user)
        starred = user.get("starred_messages", []) if user else []
        if starred:
            st.caption("Starred messages")
            for ref in starred[-5:]:
                conversation_id, message_id = ref.rsplit("::", 1)
                st.caption(message_preview(conversation_id, find_message(conversation_id, message_id), 90))


def render_device_manager(current_user: str) -> None:
    with st.expander("Devices", expanded=False):
        sessions = st.session_state.data.setdefault("device_sessions", {}).setdefault(current_user, [])
        active_sessions = [session for session in sessions if session.get("active")]
        st.caption(f"{len(active_sessions)} active session(s)")
        for session in active_sessions[-5:]:
            st.caption(f"{session.get('label', 'Session')} | {session.get('last_seen_at', '')}")
        if st.button("Logout from all devices", key=f"logout_all_{current_user}", use_container_width=True):
            logout_all_devices(current_user)
            logout()
            st.rerun()


def render_admin_moderation(current_user: str) -> None:
    if current_user != "demo":
        return
    with st.expander("Admin moderation", expanded=False):
        open_items = [
            item
            for item in st.session_state.data.get("moderation_queue", [])
            if item.get("status") == "open"
        ]
        reports = st.session_state.data.get("reports", [])
        st.caption(f"{len(open_items)} flagged message(s), {len(reports)} report(s)")
        for item in open_items[-8:]:
            message = find_message(item.get("conversation_id", ""), item.get("message_id", ""))
            st.warning(
                f"@{item.get('sender')} | {', '.join(item.get('flags', []))} | "
                f"{message_preview(item.get('conversation_id', ''), message, 100)}"
            )
            if st.button("Resolve", key=f"resolve_mod_{item['id']}", use_container_width=True):
                item["status"] = "resolved"
                item["resolved_at"] = current_stamp()
                save_data(st.session_state.data)
                st.rerun()


def render_sidebar(current_user: str) -> None:
    user = get_user(current_user)
    if not user:
        return

    with st.sidebar:
        unread = total_unread(current_user)
        badge = f'<span class="notify-badge">{unread} unread</span>' if unread else ""
        st.markdown(
            f"""
            <div class="sidebar-top">
                <div class="brand-row">
                    <div>
                        <div class="brand-title">ChatLite</div>
                        <div class="header-status"><span class="status-dot"></span>@{escape(current_user)} {badge}</div>
                    </div>
                    {avatar_html(user)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        render_profile_editor(current_user)
        render_security_backup_tools(current_user)
        render_device_manager(current_user)
        render_user_activity_dashboard(current_user)
        render_admin_moderation(current_user)
        if st.button("Log out", key="logout", use_container_width=True):
            logout()
            st.rerun()

        st.markdown('<div class="search-wrap">', unsafe_allow_html=True)
        query = st.text_input(
            "Search",
            label_visibility="collapsed",
            placeholder="Search chats and messages",
            key=f"chat_search_{current_user}",
        )
        st.markdown("</div>", unsafe_allow_html=True)
        show_archived = st.checkbox("Show archived chats", key=f"show_archived_{current_user}")

        items = ranked_chat_items(current_user, chat_items(current_user, show_archived=show_archived), query)
        st.markdown('<div class="section-title">Chats</div>', unsafe_allow_html=True)
        if items:
            for item in items:
                st.markdown(render_chat_item(current_user, item), unsafe_allow_html=True)
                if st.button(
                    f"Open {item['title']}",
                    key=f"open_{safe_key(item['conversation_id'])}",
                    use_container_width=True,
                ):
                    open_chat_item(item)
                    st.rerun()
        else:
            st.markdown('<div class="empty-side">No chats found</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-title">Add Friend</div>', unsafe_allow_html=True)
        with st.form("friend_request_form", clear_on_submit=True):
            target_username = st.text_input(
                "Friend username",
                label_visibility="collapsed",
                placeholder="Enter username or mail ID",
                key=f"friend_request_target_{current_user}",
            )
            request_submitted = st.form_submit_button("Send request", use_container_width=True)
        if request_submitted:
            success, message = send_friend_request(current_user, target_username)
            if success:
                st.success(message)
            else:
                st.warning(message)

        render_contact_and_invite_tools(current_user)
        render_group_creator(current_user)
        render_recommendations(current_user)

        incoming = incoming_requests(current_user)
        outgoing = outgoing_requests(current_user)
        st.markdown('<div class="section-title">Requests</div>', unsafe_allow_html=True)
        if incoming:
            for request in incoming:
                render_request_card(request, current_user)
        else:
            st.markdown('<div class="empty-side">No incoming requests</div>', unsafe_allow_html=True)

        if outgoing:
            st.markdown('<div class="section-title">Sent</div>', unsafe_allow_html=True)
            for request in outgoing:
                target = get_user(request["to"])
                if target:
                    st.markdown(
                        f'<div class="empty-side">@{escape(target["username"])} pending</div>',
                        unsafe_allow_html=True,
                    )


def render_header(
    title: str,
    subtitle: str,
    avatar: str,
    conversation_id: str,
    current_user: str,
) -> None:
    typing = typing_label(current_user, conversation_id)
    typing_html = f'<div class="typing-pill">{escape(typing)}</div>' if typing else ""
    header_html = (
        '<div class="chat-header">'
        '<div class="header-left">'
        f"{avatar}"
        '<div style="min-width:0">'
        f'<div class="header-name">{escape(title)}</div>'
        f'<div class="header-status">{escape(subtitle)}</div>'
        f'<div class="security-pill">{escape(encryption_status_label())}</div>'
        f"{typing_html}"
        "</div>"
        "</div>"
        '<div class="header-actions">'
        '<div class="toolbar-btn" title="Search">&#128269;</div>'
        '<div class="toolbar-btn" title="More">&#8942;</div>'
        "</div>"
        "</div>"
    )
    st.markdown(header_html, unsafe_allow_html=True)


def render_chat_tools(current_user: str, conversation_id: str, friend_username: str | None, group_id: str | None) -> str:
    user = get_user(current_user)
    search_key = f"in_chat_search_{safe_key(conversation_id)}"
    with st.expander("Chat tools", expanded=False):
        search_term = st.text_input("Search in this chat", key=search_key)
        summary_key = f"summary_{safe_key(conversation_id)}"
        summary_col, unread_col = st.columns([0.62, 0.38])
        with unread_col:
            unread_only = st.checkbox("Unread only", key=f"summary_unread_{safe_key(conversation_id)}")
        with summary_col:
            if st.button("Summarize chat", key=f"summarize_{safe_key(conversation_id)}", use_container_width=True):
                st.session_state[summary_key] = summarize_conversation(current_user, conversation_id, unread_only)
        if st.session_state.get(summary_key):
            st.info(st.session_state[summary_key])

        call_col, export_col = st.columns(2)
        with call_col:
            call_type = st.selectbox("Call type", CALL_TYPES, key=f"call_type_{safe_key(conversation_id)}")
            if st.button("Add call history", key=f"call_{safe_key(conversation_id)}", use_container_width=True):
                success, message = start_call(current_user, conversation_id, call_type)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.warning(message)
            recent_calls = [
                call
                for call in st.session_state.data.get("calls", [])
                if call.get("conversation_id") == conversation_id
            ][:3]
            for call in recent_calls:
                st.caption(f"{call.get('type', 'voice')} call | {call.get('started_at', '')} | {call.get('status', '')}")
        with export_col:
            st.download_button(
                "Export text",
                data=export_chat_text(current_user, conversation_id),
                file_name=f"chatlite-{safe_key(conversation_id)}.txt",
                mime="text/plain",
                key=f"export_txt_{safe_key(conversation_id)}",
                use_container_width=True,
            )
            st.download_button(
                "Export PDF",
                data=export_chat_pdf_bytes(current_user, conversation_id),
                file_name=f"chatlite-{safe_key(conversation_id)}.pdf",
                mime="application/pdf",
                key=f"export_pdf_{safe_key(conversation_id)}",
                use_container_width=True,
            )

        pin_col, archive_col = st.columns(2)
        with pin_col:
            pin_label = "Unpin chat" if user and is_pinned(user, conversation_id) else "Pin chat"
            if st.button(pin_label, key=f"pin_{safe_key(conversation_id)}", use_container_width=True):
                toggle_pin(current_user, conversation_id)
                st.rerun()
        with archive_col:
            archive_label = "Unarchive chat" if user and is_archived(user, conversation_id) else "Archive chat"
            if st.button(archive_label, key=f"archive_{safe_key(conversation_id)}", use_container_width=True):
                toggle_archive(current_user, conversation_id)
                st.rerun()

        if friend_username:
            friend = get_user(friend_username)
            blocked_by_me = friend_username in user.get("blocked_users", []) if user else False
            block_col, report_col = st.columns(2)
            with block_col:
                if st.button(
                    "Unblock user" if blocked_by_me else "Block user",
                    key=f"block_{friend_username}",
                    use_container_width=True,
                ):
                    if blocked_by_me:
                        unblock_user(current_user, friend_username)
                    else:
                        block_user(current_user, friend_username)
                    st.rerun()
            with report_col:
                report_reason = st.text_input("Report reason", key=f"report_reason_{friend_username}")
                if st.button("Report", key=f"report_{friend_username}", use_container_width=True):
                    success, message = report_user(current_user, friend_username, report_reason)
                    if success:
                        st.success(message)
                    else:
                        st.warning(message)
            if blocked_between(current_user, friend_username):
                target_name = friend["display_name"] if friend else friend_username
                st.warning(f"Messaging is blocked with {target_name}.")

        if group_id:
            group = get_group(group_id)
            if group:
                with st.expander("Group poll", expanded=False):
                    poll_question = st.text_input("Poll question", key=f"poll_question_{group_id}")
                    poll_options = st.text_area(
                        "Poll options",
                        placeholder="One option per line",
                        key=f"poll_options_{group_id}",
                    )
                    if st.button("Create poll", key=f"create_poll_{group_id}", use_container_width=True):
                        success, message = create_poll_message(
                            current_user,
                            conversation_id,
                            poll_question,
                            poll_options.splitlines(),
                        )
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.warning(message)

                role_line = ", ".join(f"@{member} ({group_role(group, member)})" for member in group["members"])
                st.caption(f"Owner: @{group['admin']} | Members: {role_line}")
                st.text_input("Group invite code", value=group.get("invite_code", ""), disabled=True, key=f"invite_code_{group_id}")
                if group_role(group, current_user) == "muted":
                    st.warning("You are muted in this group.")
                if can_manage_group(group, current_user):
                    approval_required = st.checkbox(
                        "Require admin approval for invite joins",
                        value=bool(group.get("approval_required")),
                        key=f"group_approval_{group_id}",
                    )
                    if approval_required != bool(group.get("approval_required")):
                        group["approval_required"] = approval_required
                        save_data(st.session_state.data)
                        st.rerun()
                    pending_requests = [
                        request
                        for request in group.get("join_requests", [])
                        if request.get("status") == "pending"
                    ]
                    for request in pending_requests:
                        requester = get_user(request.get("username", ""))
                        st.caption(f"Join request: @{request.get('username')} {requester.get('display_name', '') if requester else ''}")
                        approve_col, decline_col = st.columns(2)
                        with approve_col:
                            if st.button("Approve", key=f"approve_join_{request['id']}", use_container_width=True):
                                respond_group_join(group_id, request["id"], True)
                                st.rerun()
                        with decline_col:
                            if st.button("Decline", key=f"decline_join_{request['id']}", use_container_width=True):
                                respond_group_join(group_id, request["id"], False)
                                st.rerun()
                    friends = [friend["username"] for friend in sorted_friend_users(current_user)]
                    add_options = [friend for friend in friends if friend not in group["members"]]
                    remove_options = [
                        member
                        for member in group["members"]
                        if member != current_user and member != group.get("admin")
                    ]
                    add_members = st.multiselect("Add members", add_options, key=f"group_add_{group_id}")
                    remove_members = st.multiselect("Remove members", remove_options, key=f"group_remove_{group_id}")
                    if st.button("Update group members", key=f"group_update_{group_id}", use_container_width=True):
                        update_group_members(group_id, add_members, remove_members)
                        st.rerun()
                if can_change_group_roles(group, current_user):
                    role_candidates = [member for member in group["members"] if member != group.get("admin")]
                    if role_candidates:
                        role_member = st.selectbox("Member role", role_candidates, key=f"group_role_member_{group_id}")
                        current_role = group_role(group, role_member)
                        role_options = ["admin", "member", "muted"]
                        role_choice = st.selectbox(
                            "Role",
                            role_options,
                            index=role_options.index(current_role) if current_role in role_options else 1,
                            key=f"group_role_choice_{group_id}",
                        )
                        if st.button("Update role", key=f"group_role_update_{group_id}", use_container_width=True):
                            success, message = set_group_role(group_id, role_member, role_choice, current_user)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.warning(message)
                if st.button("Leave group", key=f"leave_group_{group_id}", use_container_width=True):
                    leave_group(group_id, current_user)
                    st.rerun()
        return search_term


def render_messages(current_user: str, conversation_id: str, search_term: str = "") -> None:
    messages = st.session_state.data["messages"].get(conversation_id, [])
    rows = []
    needle = search_term.strip().lower()
    if needle:
        scored_messages = [
            (message_search_score(conversation_id, message, needle), timestamp_sort_value(message.get("created_at")), message)
            for message in messages
        ]
        visible_messages = [message for score, _, message in sorted(scored_messages, key=lambda value: (-value[0], -value[1])) if score > 0]
    else:
        visible_messages = messages
    for message in visible_messages:
        text = message_text(conversation_id, message)
        sender_class = "me" if message.get("sender") == current_user else "them"
        sender = get_user(message.get("sender", ""))
        sender_name = sender["display_name"] if sender else message.get("sender", "")
        sender_html = ""
        if is_group_conversation(conversation_id) and sender_class == "them":
            sender_html = f'<div class="message-sender">{escape(sender_name)}</div>'
        edited = '<span class="edited-label">edited</span>' if message.get("edited_at") and not message.get("deleted") else ""
        deleted_class = " deleted-message" if message.get("deleted") else ""
        flags = message.get("moderation_flags", [])
        flag_html = ""
        if flags and not message.get("deleted"):
            flag_html = f'<div class="moderation-flag">Flagged: {escape(", ".join(flags[:3]))}</div>'
        rows.append(
            f'<div class="message-row {sender_class}">'
            f'<div class="message-bubble{deleted_class}">'
            f"{sender_html}"
            f"{reply_html(conversation_id, message)}"
            f"{message_labels_html(message)}"
            f"<div>{escape(text)}</div>"
            f"{poll_html(message)}"
            f"{total_attachments_html(message)}"
            f"{reactions_html(message)}"
            f"{flag_html}"
            '<div class="message-meta">'
            f"{edited}<span>{escape(message.get('time', ''))}</span>"
            f"{receipt_html(conversation_id, message, current_user)}"
            "</div>"
            "</div>"
            "</div>"
        )
    if not rows:
        st.markdown('<div class="empty-state">No messages found</div>', unsafe_allow_html=True)
        return
    st.markdown(f'<div class="chat-wall">{"".join(rows)}</div>', unsafe_allow_html=True)


def render_composer(current_user: str, conversation_id: str, disabled: bool = False) -> None:
    key = safe_key(conversation_id)
    input_key = f"message_input_{key}"
    clear_key = f"clear_message_input_{key}"
    upload_nonce_key = f"upload_nonce_{key}"
    st.session_state.setdefault(upload_nonce_key, 0)
    if st.session_state.pop(clear_key, False):
        st.session_state[input_key] = ""
        st.session_state[upload_nonce_key] += 1

    with st.container(key=f"composer-{key}"):
        suggestions = smart_reply_suggestions(current_user, conversation_id)
        suggestion_cols = st.columns(len(suggestions))
        for index, suggestion in enumerate(suggestions):
            with suggestion_cols[index]:
                if st.button(
                    suggestion,
                    key=f"suggest_{key}_{index}",
                    use_container_width=True,
                    disabled=disabled,
                ):
                    st.session_state[input_key] = suggestion
                    st.rerun()
        message_col, send_col = st.columns([1, 0.16], gap="small", vertical_alignment="bottom")
        with message_col:
            draft = st.text_input(
                "Type a message",
                label_visibility="collapsed",
                placeholder="Type a message",
                key=input_key,
                disabled=disabled,
            )
        with send_col:
            submitted = st.button(
                "Send",
                icon=":material/send:",
                type="primary",
                use_container_width=True,
                key=f"send_{key}",
                disabled=disabled,
            )
        uploads = file_uploader_compat(
            "Attach media or files",
            file_types=MEDIA_EXTENSIONS,
            accept_multiple_files=True,
            max_upload_size=upload_limit_mb(),
            key=f"media_{key}_{st.session_state[upload_nonce_key]}",
            disabled=disabled,
        )
        recent_messages = [
            message
            for message in st.session_state.data["messages"].get(conversation_id, [])[-10:]
            if not message.get("deleted")
        ]
        reply_options = [""] + [message["id"] for message in recent_messages]
        reply_to = st.selectbox(
            "Reply to",
            reply_options,
            format_func=lambda message_id: "No reply"
            if not message_id
            else message_option_label(conversation_id, find_message(conversation_id, message_id) or {}),
            key=f"reply_to_{key}",
            disabled=disabled,
        )
        composer_cols = st.columns(3)
        with composer_cols[0]:
            disappear_label = st.selectbox(
                "Disappearing",
                list(DISAPPEARING_OPTIONS),
                key=f"disappear_{key}",
                disabled=disabled,
            )
        with composer_cols[1]:
            schedule_enabled = st.checkbox("Schedule", key=f"schedule_enabled_{key}", disabled=disabled)
        with composer_cols[2]:
            schedule_date = st.date_input("Send date", key=f"schedule_date_{key}", disabled=disabled or not schedule_enabled)
        schedule_time = st.time_input("Send time", key=f"schedule_time_{key}", disabled=disabled or not schedule_enabled)

    if disabled:
        typing = st.session_state.data.setdefault("typing", {}).setdefault(conversation_id, {})
        if current_user in typing:
            clear_typing(current_user, conversation_id)
            save_data(st.session_state.data)
    else:
        record_typing(current_user, conversation_id, draft)
    if submitted:
        attachments: list[dict[str, Any]] = []
        for upload in uploads or []:
            success, result = uploaded_file_to_attachment(upload)
            if not success:
                st.warning(str(result))
                return
            attachments.append(result)
        expires_at = expiry_from_seconds(DISAPPEARING_OPTIONS.get(disappear_label, 0))
        if schedule_enabled:
            send_at = datetime.combine(schedule_date, schedule_time)
            success, message = schedule_message(current_user, conversation_id, draft, send_at, reply_to, expires_at)
        else:
            success, message = add_message_to_conversation(
                current_user,
                conversation_id,
                draft,
                attachments,
                reply_to=reply_to,
                expires_at=expires_at,
            )
        if success:
            st.session_state[clear_key] = True
            st.rerun()
        else:
            st.warning(message)


def render_message_tools(current_user: str, conversation_id: str) -> None:
    all_messages = [
        message
        for message in st.session_state.data["messages"].get(conversation_id, [])
        if not message.get("deleted")
    ]
    if all_messages:
        with st.expander("Message actions", expanded=False):
            message_by_id = {message["id"]: message for message in all_messages[-30:]}
            selected_action_id = st.selectbox(
                "Select message",
                list(message_by_id),
                format_func=lambda message_id: message_option_label(conversation_id, message_by_id[message_id]),
                key=f"message_action_select_{safe_key(conversation_id)}",
            )
            selected_action = message_by_id[selected_action_id]
            action_cols = st.columns(3)
            with action_cols[0]:
                reaction = st.selectbox(
                    "Reaction",
                    REACTION_OPTIONS,
                    key=f"reaction_select_{safe_key(conversation_id)}",
                )
                if st.button("React", key=f"react_{selected_action_id}", use_container_width=True):
                    success, message = toggle_reaction(conversation_id, selected_action_id, current_user, reaction)
                    if success:
                        st.rerun()
                    st.warning(message)
            with action_cols[1]:
                star_label = "Unstar" if current_user in selected_action.get("starred_by", []) else "Star"
                if st.button(star_label, key=f"star_{selected_action_id}", use_container_width=True):
                    success, message = toggle_star_message(conversation_id, selected_action_id, current_user)
                    if success:
                        st.rerun()
                    st.warning(message)
            with action_cols[2]:
                forward_items = chat_items(current_user, show_archived=True)
                forward_ids = [item["conversation_id"] for item in forward_items if item["conversation_id"] != conversation_id]
                if forward_ids:
                    forward_to = st.selectbox(
                        "Forward to",
                        forward_ids,
                        format_func=lambda item_id: next(item["title"] for item in forward_items if item["conversation_id"] == item_id),
                        key=f"forward_to_{safe_key(conversation_id)}",
                    )
                    if st.button("Forward", key=f"forward_{selected_action_id}", use_container_width=True):
                        success, message = forward_message(conversation_id, selected_action_id, current_user, forward_to)
                        if success:
                            st.success(message)
                        else:
                            st.warning(message)

            if selected_action.get("poll"):
                poll_options = selected_action["poll"].get("options", [])
                option_ids = [option["id"] for option in poll_options]
                vote_for = st.selectbox(
                    "Poll vote",
                    option_ids,
                    format_func=lambda option_id: next(option["text"] for option in poll_options if option["id"] == option_id),
                    key=f"poll_vote_{selected_action_id}",
                )
                if st.button("Vote", key=f"vote_{selected_action_id}", use_container_width=True):
                    success, message = vote_poll(conversation_id, selected_action_id, vote_for, current_user)
                    if success:
                        st.rerun()
                    st.warning(message)

    own_messages = [
        message
        for message in st.session_state.data["messages"].get(conversation_id, [])
        if message.get("sender") == current_user and not message.get("deleted")
    ]
    if not own_messages:
        return
    with st.expander("Edit or delete sent message", expanded=False):
        message_by_id = {message["id"]: message for message in own_messages}
        selected_id = st.selectbox(
            "Message",
            list(message_by_id),
            format_func=lambda message_id: message_option_label(conversation_id, message_by_id[message_id]),
            key=f"message_tool_select_{safe_key(conversation_id)}",
        )
        selected = message_by_id[selected_id]
        new_text = st.text_area(
            "Edit text",
            value=message_text(conversation_id, selected),
            key=f"message_edit_{selected['id']}",
        )
        edit_col, delete_col = st.columns(2)
        with edit_col:
            if st.button("Save edit", key=f"save_edit_{selected['id']}", use_container_width=True):
                success, message = edit_message(conversation_id, selected["id"], new_text, current_user)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.warning(message)
        with delete_col:
            if st.button("Delete for everyone", key=f"delete_msg_{selected['id']}", use_container_width=True):
                success, message = delete_message(conversation_id, selected["id"], current_user)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.warning(message)


def render_empty_chat() -> None:
    with st.container(key="chat-shell"):
        st.markdown(
            """
            <div class="chat-header">
                <div class="header-left">
                    <div class="avatar" style="background:#04986d">CL</div>
                    <div>
                        <div class="header-name">ChatLite</div>
                        <div class="header-status">No chat selected</div>
                    </div>
                </div>
            </div>
            <div class="empty-state">Add a friend, create a group, or select a chat</div>
            """,
            unsafe_allow_html=True,
        )


def active_conversation_id(current_user: str) -> str | None:
    if st.session_state.get("active_group"):
        return group_chat_id(st.session_state.active_group)
    if st.session_state.get("active_friend"):
        return private_chat_id(current_user, st.session_state.active_friend)
    return None


def initialize_state() -> None:
    if "data" not in st.session_state:
        st.session_state.data = load_data()
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "active_friend" not in st.session_state:
        st.session_state.active_friend = None
    if "active_group" not in st.session_state:
        st.session_state.active_group = None
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None
    if "last_unread_total" not in st.session_state:
        st.session_state.last_unread_total = 0
    if "last_important_unread" not in st.session_state:
        st.session_state.last_important_unread = 0

    current_user = st.session_state.current_user
    clean_expired_messages()
    deliver_due_scheduled_messages()
    if not current_user:
        return

    if not current_session_is_active(current_user):
        st.session_state.current_user = None
        st.session_state.current_session_id = None
        st.session_state.active_friend = None
        st.session_state.active_group = None
        st.query_params.clear()
        st.warning("This session was logged out from another device.")
        return

    touch_presence(current_user)
    flush_offline_queue(current_user)
    for item in chat_items(current_user, show_archived=True):
        mark_conversation_delivered(current_user, item["conversation_id"])
    friends = {friend["username"] for friend in sorted_friend_users(current_user)}
    groups = {
        group_id
        for group_id, group in st.session_state.data["groups"].items()
        if current_user in group.get("members", [])
    }

    chat_from_url = st.query_params.get("chat")
    group_from_url = st.query_params.get("group")
    if group_from_url in groups:
        st.session_state.active_group = group_from_url
        st.session_state.active_friend = None
    elif chat_from_url in friends:
        st.session_state.active_friend = chat_from_url
        st.session_state.active_group = None

    if st.session_state.active_group not in groups:
        st.session_state.active_group = None
    if st.session_state.active_friend not in friends:
        st.session_state.active_friend = None

    if not active_conversation_id(current_user):
        items = chat_items(current_user, show_archived=False)
        if items:
            first = items[0]
            st.session_state.active_group = first.get("group_id")
            st.session_state.active_friend = first.get("friend_username")

    active_id = active_conversation_id(current_user)
    if active_id:
        mark_conversation_read(current_user, active_id)


def show_notifications(current_user: str) -> None:
    unread = total_unread(current_user)
    important_unread = important_unread_count(current_user)
    if important_unread > st.session_state.get("last_important_unread", 0):
        st.toast(f"{important_unread} important unread message(s)")
    st.session_state.last_unread_total = unread
    st.session_state.last_important_unread = important_unread


def render_chat_app() -> None:
    current_user = st.session_state.current_user
    show_notifications(current_user)
    render_sidebar(current_user)
    conversation_id = active_conversation_id(current_user)
    if not conversation_id:
        render_empty_chat()
        return

    friend_username = st.session_state.get("active_friend")
    group_id = st.session_state.get("active_group")
    disabled = False
    if group_id:
        group = get_group(group_id)
        if not group or current_user not in group.get("members", []):
            render_empty_chat()
            return
        title = group["name"]
        subtitle = f"{len(group['members'])} members | {group_role(group, current_user)}"
        avatar = group_avatar_html(group)
        disabled = not can_send_to_group(group, current_user)
    else:
        friend = get_user(friend_username)
        if not friend or not are_friends(current_user, friend_username):
            render_empty_chat()
            return
        title = friend["display_name"]
        subtitle = f"{presence_label(friend)} | {profile_contact_line(friend)}"
        avatar = avatar_html(friend)
        disabled = blocked_between(current_user, friend_username)

    with st.container(key="chat-shell"):
        render_realtime_bridge(conversation_id, current_user)
        render_header(title, subtitle, avatar, conversation_id, current_user)
        search_term = render_chat_tools(current_user, conversation_id, friend_username, group_id)
        render_messages(current_user, conversation_id, search_term)
        render_composer(current_user, conversation_id, disabled=disabled)
        render_message_tools(current_user, conversation_id)


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon=":speech_balloon:", layout="wide")
    initialize_state()
    inject_styles()

    if st.session_state.current_user:
        render_chat_app()
    else:
        render_auth_screen()


if __name__ == "__main__":
    main()
