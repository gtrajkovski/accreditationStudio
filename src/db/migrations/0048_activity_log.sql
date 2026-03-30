CREATE TABLE IF NOT EXISTS activity_log (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    user_name TEXT,
    institution_id TEXT,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    details TEXT,
    ip_address TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_log(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_institution ON activity_log(institution_id);
CREATE INDEX IF NOT EXISTS idx_activity_action ON activity_log(action);
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at);
CREATE INDEX IF NOT EXISTS idx_activity_entity ON activity_log(entity_type, entity_id);
