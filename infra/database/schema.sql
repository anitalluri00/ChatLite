-- ChatLite normalized PostgreSQL schema.
-- Use this when moving away from the current single-state JSONB storage.

CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    country_code TEXT DEFAULT '+91',
    phone_number TEXT DEFAULT '',
    photo_data_uri TEXT DEFAULT '',
    status TEXT DEFAULT 'available',
    trust_score INTEGER DEFAULT 80,
    abuse_score INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_seen_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS device_sessions (
    id UUID PRIMARY KEY,
    username TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    label TEXT NOT NULL,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_seen_at TIMESTAMPTZ DEFAULT now(),
    ended_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('private', 'group')),
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversation_members (
    conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,
    username TEXT REFERENCES users(username) ON DELETE CASCADE,
    role TEXT DEFAULT 'member',
    joined_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (conversation_id, username)
);

CREATE TABLE IF NOT EXISTS groups (
    id TEXT PRIMARY KEY,
    conversation_id TEXT UNIQUE REFERENCES conversations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    owner_username TEXT REFERENCES users(username),
    invite_code TEXT UNIQUE NOT NULL,
    approval_required BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender TEXT NOT NULL REFERENCES users(username),
    ciphertext TEXT,
    encrypted BOOLEAN DEFAULT true,
    key_version INTEGER DEFAULT 1,
    compressed BOOLEAN DEFAULT false,
    reply_to UUID REFERENCES messages(id),
    forwarded_from UUID REFERENCES messages(id),
    state TEXT DEFAULT 'sent',
    expires_at TIMESTAMPTZ,
    edited_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS message_receipts (
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    username TEXT REFERENCES users(username) ON DELETE CASCADE,
    state TEXT NOT NULL CHECK (state IN ('delivered', 'read')),
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (message_id, username)
);

CREATE TABLE IF NOT EXISTS message_reactions (
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    username TEXT REFERENCES users(username) ON DELETE CASCADE,
    reaction TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (message_id, username, reaction)
);

CREATE TABLE IF NOT EXISTS attachments (
    hash TEXT PRIMARY KEY,
    mime_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    stored_size_bytes BIGINT NOT NULL,
    storage_backend TEXT DEFAULT 'local',
    object_key TEXT DEFAULT '',
    scan_status TEXT DEFAULT 'clean',
    thumbnail_object_key TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS message_attachments (
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    attachment_hash TEXT REFERENCES attachments(hash),
    filename TEXT NOT NULL,
    PRIMARY KEY (message_id, attachment_hash, filename)
);

CREATE TABLE IF NOT EXISTS polls (
    id UUID PRIMARY KEY,
    message_id UUID UNIQUE REFERENCES messages(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    closed BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS poll_options (
    id UUID PRIMARY KEY,
    poll_id UUID REFERENCES polls(id) ON DELETE CASCADE,
    option_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS poll_votes (
    poll_id UUID REFERENCES polls(id) ON DELETE CASCADE,
    option_id UUID REFERENCES poll_options(id) ON DELETE CASCADE,
    username TEXT REFERENCES users(username) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (poll_id, username)
);

CREATE TABLE IF NOT EXISTS moderation_events (
    id UUID PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,
    message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    sender TEXT REFERENCES users(username),
    severity TEXT DEFAULT 'review',
    flags JSONB NOT NULL DEFAULT '[]',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
    ON messages (conversation_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_messages_sender_created
    ON messages (sender, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_messages_expires_at
    ON messages (expires_at)
    WHERE expires_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_moderation_status_created
    ON moderation_events (status, created_at DESC);
