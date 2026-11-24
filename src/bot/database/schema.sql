CREATE TABLE IF NOT EXISTS channels (
    channel_id TEXT PRIMARY KEY,
    title TEXT,
    username TEXT,
    owner_id INTEGER NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id INTEGER NOT NULL,
    channel_id TEXT,
    text TEXT,
    media_json TEXT DEFAULT '[]',
    buttons_json TEXT DEFAULT '[]',
    scheduled_at TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    telegram_message_ids TEXT DEFAULT '[]',
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER,
    file_id TEXT NOT NULL,
    media_type TEXT NOT NULL,
    caption TEXT,
    position INTEGER DEFAULT 0,
    FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_posts_owner ON posts(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_posts_status_scheduled ON posts(status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_channels_owner ON channels(owner_id);
