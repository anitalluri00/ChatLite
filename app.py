from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import random
import re
import sqlite3
import uuid
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import streamlit as st

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
except ImportError:
    Fernet = None
    InvalidToken = Exception

try:
    import psycopg
    from psycopg.types.json import Jsonb
except ImportError:
    psycopg = None
    Jsonb = None


APP_TITLE = "ChatLite"
APP_SECRET = os.getenv("CHATLITE_APP_SECRET", "chatlite-local-development-secret")
DATABASE_URL = os.getenv("CHATLITE_DATABASE_URL") or os.getenv("DATABASE_URL", "")
SQLITE_FILE = Path(os.getenv("CHATLITE_SQLITE_FILE", "chatlite_data.sqlite3")).expanduser()
LEGACY_DATA_FILE = Path(os.getenv("CHATLITE_DATA_FILE", "chatlite_data.json")).expanduser()
STORAGE_BACKEND = os.getenv("CHATLITE_STORAGE_BACKEND", "").strip().lower()
USERNAME_PATTERN = re.compile(r"^[a-z0-9_]{3,20}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^[0-9][0-9 .()/-]{4,24}$")
ACCENTS = ["#04986d", "#2f80ed", "#f59e0b", "#7c3aed", "#e11d48", "#0f766e"]
THEMES = ["Light", "Dark"]
GROUP_PREFIX = "group::"
MAX_ATTACHMENT_BYTES = int(os.getenv("CHATLITE_MAX_ATTACHMENT_BYTES", "2500000"))
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


def timestamp_sort_value(value: str | None) -> float:
    parsed = parse_stamp(value)
    return parsed.timestamp() if parsed else 0.0


def upload_limit_mb() -> int:
    return max(1, (MAX_ATTACHMENT_BYTES + 999_999) // 1_000_000)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


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


def chat_cipher(conversation_id: str) -> Fernet | None:
    if not Fernet:
        return None
    digest = hashlib.sha256(f"{APP_SECRET}:{conversation_id}".encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encryption_status_label() -> str:
    return "Encrypted storage" if Fernet else "Encryption unavailable"


def encrypted_message_payload(conversation_id: str, text: str) -> dict[str, Any]:
    cipher = chat_cipher(conversation_id)
    if not cipher:
        return {"text": text, "encrypted": False}
    token = cipher.encrypt(text.encode("utf-8")).decode("ascii")
    return {
        "ciphertext": token,
        "encrypted": True,
        "algorithm": "fernet-chat-key-v1",
    }


def message_text(conversation_id: str, message: dict[str, Any]) -> str:
    if message.get("deleted"):
        return "This message was deleted."
    if not message.get("encrypted"):
        return message.get("text", "")

    cipher = chat_cipher(conversation_id)
    if not cipher:
        return "Encrypted message unavailable"
    try:
        return cipher.decrypt(message.get("ciphertext", "").encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError):
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
    return {
        "username": username,
        "display_name": display_name.strip() or username,
        "password_hash": password_hash(username, password),
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
        "schema_version": 3,
        "users": users,
        "groups": {
            group_id: {
                "id": group_id,
                "name": "Project Crew",
                "admin": "demo",
                "members": ["demo", "aisha", "michael"],
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


def ensure_data_shape(data: dict[str, Any]) -> dict[str, Any]:
    previous_version = int(data.get("schema_version", 1) or 1)
    data["schema_version"] = 3
    data.setdefault("users", {})
    data.setdefault("groups", {})
    data.setdefault("friend_requests", [])
    data.setdefault("messages", {})
    data.setdefault("reports", [])
    data.setdefault("typing", {})

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
        user.setdefault("last_seen_at", "")
        user.setdefault("online_until", "")
        user.setdefault("password_reset", {})

    for group_id, group in data["groups"].items():
        group.setdefault("id", group_id)
        group.setdefault("name", "Group chat")
        group.setdefault("admin", next(iter(group.get("members", [])), ""))
        group["members"] = sorted(set(group.get("members", [])))
        group.setdefault("photo_data_uri", "")
        group.setdefault("accent", "#2f80ed")
        group.setdefault("created_at", current_stamp())

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
            message.setdefault("delivered_to", [member for member in members if member != sender])
            if previous_version < 3:
                message.setdefault("read_by", members)
            else:
                message.setdefault("read_by", [sender])
            if message.get("encrypted") or "text" not in message or message.get("deleted"):
                continue
            plaintext = message.pop("text", "")
            message.update(encrypted_message_payload(conversation_id, plaintext))
    return data


def selected_backend() -> str:
    if STORAGE_BACKEND in {"json", "sqlite", "postgres"}:
        return STORAGE_BACKEND
    if DATABASE_URL.startswith(("postgresql://", "postgres://")):
        return "postgres"
    return "sqlite"


def sqlite_path() -> Path:
    if DATABASE_URL.startswith("sqlite:///"):
        parsed = urlparse(DATABASE_URL)
        path_text = unquote(parsed.path or "")
        if path_text.startswith("//"):
            return Path(path_text[1:]).expanduser()
        if path_text.startswith("/"):
            return Path(path_text[1:]).expanduser()
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
    try:
        save_data(shaped_data, backend=save_backend)
    except Exception as exc:
        st.error(f"Storage save error: {exc}")
    return shaped_data


def save_data(data: dict[str, Any], backend: str | None = None) -> None:
    backend = backend or selected_backend()
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
    encoded = base64.b64encode(file_bytes).decode("ascii")
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
        "category": category,
        "data_uri": f"data:{mime_type};base64,{encoded}",
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

    country_option = next(option for option in COUNTRY_CODE_OPTIONS if option["label"] == selected_country_label)
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
        "photo_data_uri": photo_data_uri,
        "accent": ACCENTS[len(st.session_state.data["groups"]) % len(ACCENTS)],
        "created_at": current_stamp(),
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
    save_data(st.session_state.data)


def leave_group(group_id: str, username: str) -> None:
    group = get_group(group_id)
    if not group:
        return
    if username == group.get("admin") and len(group["members"]) > 1:
        group["admin"] = next(member for member in group["members"] if member != username)
    group["members"] = sorted(member for member in group["members"] if member != username)
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
        if message.get("sender") == username or username in message.get("read_by", []):
            continue
        message["read_by"] = sorted(set(message.get("read_by", [])) | {username})
        changed = True
    if changed:
        save_data(st.session_state.data)


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
) -> tuple[bool, str]:
    cleaned = text.strip()
    attachments = attachments or []
    if not cleaned and not attachments:
        return False, "Type a message or attach a file."
    if not is_group_conversation(conversation_id):
        members = [member for member in conversation_members(conversation_id) if member != sender]
        if members and blocked_between(sender, members[0]):
            return False, "Messaging is blocked for this chat."
    if sender not in conversation_members(conversation_id):
        return False, "You are not a member of this chat."

    members = conversation_members(conversation_id)
    st.session_state.data["messages"].setdefault(conversation_id, []).append(
        {
            "id": str(uuid.uuid4()),
            "sender": sender,
            "time": current_time(),
            "created_at": current_stamp(),
            "edited_at": "",
            "deleted": False,
            "deleted_at": "",
            "attachments": attachments,
            "read_by": [sender],
            "delivered_to": [member for member in members if member != sender],
            **encrypted_message_payload(conversation_id, cleaned),
        }
    )
    clear_typing(sender, conversation_id)
    save_data(st.session_state.data)
    return True, "Message sent."


def edit_message(conversation_id: str, message_id: str, new_text: str, editor: str) -> tuple[bool, str]:
    cleaned = new_text.strip()
    if not cleaned:
        return False, "Message text cannot be empty."
    for message in st.session_state.data["messages"].get(conversation_id, []):
        if message["id"] == message_id and message.get("sender") == editor and not message.get("deleted"):
            message.pop("text", None)
            message.pop("ciphertext", None)
            message.update(encrypted_message_payload(conversation_id, cleaned))
            message["edited_at"] = current_stamp()
            save_data(st.session_state.data)
            return True, "Message edited."
    return False, "Message not found."


def delete_message(conversation_id: str, message_id: str, editor: str) -> tuple[bool, str]:
    for message in st.session_state.data["messages"].get(conversation_id, []):
        if message["id"] == message_id and message.get("sender") == editor and not message.get("deleted"):
            message["deleted"] = True
            message["deleted_at"] = current_stamp()
            message["attachments"] = []
            message.pop("text", None)
            message.pop("ciphertext", None)
            save_data(st.session_state.data)
            return True, "Message deleted."
    return False, "Message not found."


def receipt_html(conversation_id: str, message: dict[str, Any], current_user: str) -> str:
    if message.get("sender") != current_user:
        return ""
    others = [member for member in conversation_members(conversation_id) if member != current_user]
    read_count = sum(1 for member in others if member in message.get("read_by", []))
    delivered_count = sum(1 for member in others if member in message.get("delivered_to", []))
    if others and read_count == len(others):
        return '<span class="receipt receipt-read">&#10003;&#10003;</span>'
    if delivered_count:
        return '<span class="receipt">&#10003;&#10003;</span>'
    return '<span class="receipt">&#10003;</span>'


def record_typing(username: str, conversation_id: str, draft: str) -> None:
    typing = st.session_state.data.setdefault("typing", {}).setdefault(conversation_id, {})
    changed = False
    if draft.strip():
        stamp = current_stamp()
        if typing.get(username) != stamp:
            typing[username] = stamp
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
    username = username_for_email(email_value)
    user = get_user(username) if username else None
    if not user:
        return False, "No account found for this mail ID."
    code = f"{random.randint(100000, 999999)}"
    user["password_reset"] = {
        "code_hash": password_hash(username, code),
        "expires_at": (datetime.now() + timedelta(minutes=15)).isoformat(timespec="seconds"),
    }
    save_data(st.session_state.data)
    st.session_state.reset_code_preview = code
    return True, "Reset code generated. In production this should be sent by email."


def complete_password_reset(email_value: str, code: str, new_password: str, confirm_password: str) -> tuple[bool, str]:
    username = username_for_email(email_value)
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
    user["password_reset"] = {}
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
    st.session_state.active_friend = None
    st.session_state.active_group = None
    return True, "Account created."


def login(email_value: str, password: str) -> tuple[bool, str]:
    username = username_for_email(email_value)
    user = get_user(username) if username else None
    if not user or not verify_password(username, password, user.get("password_hash", "")):
        return False, "Invalid mail ID or password."

    st.session_state.current_user = username
    st.session_state.active_friend = None
    st.session_state.active_group = None
    touch_presence(username)
    return True, "Logged in."


def logout() -> None:
    current_user = st.session_state.get("current_user")
    if current_user:
        set_offline(current_user)
    st.session_state.current_user = None
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

    def sort_key(item: dict[str, Any]) -> tuple[int, float]:
        pinned = 0 if is_pinned(user, item["conversation_id"]) else 1
        newest_first = -timestamp_sort_value(latest_message_stamp(item["conversation_id"]))
        return (pinned, newest_first)

    return sorted(items, key=sort_key)


def conversation_matches_query(current_user: str, item: dict[str, Any], query: str) -> bool:
    if not query:
        return True
    needle = query.lower()
    if needle in item["title"].lower() or needle in item["subtitle"].lower():
        return True
    if needle in latest_message(current_user, item["conversation_id"]).lower():
        return True
    for message in st.session_state.data["messages"].get(item["conversation_id"], []):
        if needle in message_text(item["conversation_id"], message).lower():
            return True
        if any(needle in attachment.get("name", "").lower() for attachment in message.get("attachments", [])):
            return True
    return False


def total_attachments_html(message: dict[str, Any]) -> str:
    parts = []
    for attachment in message.get("attachments", []):
        name = escape(attachment.get("name", "attachment"))
        data_uri = escape(attachment.get("data_uri", ""))
        mime_type = escape(attachment.get("mime_type", ""))
        category = attachment.get("category", "file")
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
            uploaded_photo = st.file_uploader(
                "Profile photo",
                type=["jpg", "jpeg", "png", "webp"],
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
        <a class="contact-link" href="{item['href']}">
        <div class="contact-card{active}">
            {item['avatar']}
            <div style="min-width:0">
                <div class="contact-name">{escape(item['title'])}</div>
                <div class="contact-preview">{escape(latest_message(current_user, conversation_id))}</div>
            </div>
            <div class="contact-meta">{meta_html}</div>
        </div>
        </a>
    """


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
            group_photo = st.file_uploader(
                "Group photo",
                type=["jpg", "jpeg", "png", "webp"],
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

        items = [
            item
            for item in chat_items(current_user, show_archived=show_archived)
            if conversation_matches_query(current_user, item, query)
        ]
        st.markdown('<div class="section-title">Chats</div>', unsafe_allow_html=True)
        if items:
            for item in items:
                st.markdown(render_chat_item(current_user, item), unsafe_allow_html=True)
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

        render_group_creator(current_user)

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
                st.caption(f"Admin: @{group['admin']} | Members: {', '.join('@' + member for member in group['members'])}")
                if group.get("admin") == current_user:
                    friends = [friend["username"] for friend in sorted_friend_users(current_user)]
                    add_options = [friend for friend in friends if friend not in group["members"]]
                    remove_options = [member for member in group["members"] if member != current_user]
                    add_members = st.multiselect("Add members", add_options, key=f"group_add_{group_id}")
                    remove_members = st.multiselect("Remove members", remove_options, key=f"group_remove_{group_id}")
                    if st.button("Update group members", key=f"group_update_{group_id}", use_container_width=True):
                        update_group_members(group_id, add_members, remove_members)
                        st.rerun()
                if st.button("Leave group", key=f"leave_group_{group_id}", use_container_width=True):
                    leave_group(group_id, current_user)
                    st.rerun()
        return search_term


def render_messages(current_user: str, conversation_id: str, search_term: str = "") -> None:
    messages = st.session_state.data["messages"].get(conversation_id, [])
    rows = []
    needle = search_term.strip().lower()
    for message in messages:
        text = message_text(conversation_id, message)
        attachment_names = " ".join(attachment.get("name", "") for attachment in message.get("attachments", []))
        if needle and needle not in text.lower() and needle not in attachment_names.lower():
            continue
        sender_class = "me" if message["sender"] == current_user else "them"
        sender = get_user(message.get("sender", ""))
        sender_name = sender["display_name"] if sender else message.get("sender", "")
        sender_html = ""
        if is_group_conversation(conversation_id) and sender_class == "them":
            sender_html = f'<div class="message-sender">{escape(sender_name)}</div>'
        edited = '<span class="edited-label">edited</span>' if message.get("edited_at") and not message.get("deleted") else ""
        deleted_class = " deleted-message" if message.get("deleted") else ""
        rows.append(
            f'<div class="message-row {sender_class}">'
            f'<div class="message-bubble{deleted_class}">'
            f"{sender_html}"
            f"<div>{escape(text)}</div>"
            f"{total_attachments_html(message)}"
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
        uploads = st.file_uploader(
            "Attach media or files",
            type=MEDIA_EXTENSIONS,
            accept_multiple_files=True,
            max_upload_size=upload_limit_mb(),
            key=f"media_{key}_{st.session_state[upload_nonce_key]}",
            disabled=disabled,
        )

    record_typing(current_user, conversation_id, draft)
    if submitted:
        attachments: list[dict[str, Any]] = []
        for upload in uploads or []:
            success, result = uploaded_file_to_attachment(upload)
            if not success:
                st.warning(str(result))
                return
            attachments.append(result)
        success, message = add_message_to_conversation(current_user, conversation_id, draft, attachments)
        if success:
            st.session_state[clear_key] = True
            st.rerun()
        else:
            st.warning(message)


def render_message_tools(current_user: str, conversation_id: str) -> None:
    own_messages = [
        message
        for message in st.session_state.data["messages"].get(conversation_id, [])
        if message.get("sender") == current_user and not message.get("deleted")
    ]
    if not own_messages:
        return
    with st.expander("Edit or delete sent message", expanded=False):
        labels = []
        for message in own_messages:
            text = message_text(conversation_id, message)
            attachment_label = " attachment" if message.get("attachments") else ""
            labels.append(f"{message.get('time', '')} - {(text or attachment_label)[:48]}")
        selected_label = st.selectbox("Message", labels, key=f"message_tool_select_{safe_key(conversation_id)}")
        selected = own_messages[labels.index(selected_label)]
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
    if "last_unread_total" not in st.session_state:
        st.session_state.last_unread_total = 0

    current_user = st.session_state.current_user
    if not current_user:
        return

    touch_presence(current_user)
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
    if unread > st.session_state.get("last_unread_total", 0):
        st.toast(f"{unread} unread message(s)")
    st.session_state.last_unread_total = unread


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
        subtitle = f"{len(group['members'])} members"
        avatar = group_avatar_html(group)
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
