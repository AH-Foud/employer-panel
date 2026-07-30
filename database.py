import sqlite3
import json
import os
from config import DATA_DIR

DB_PATH = os.path.join(DATA_DIR, "database.db")

def get_conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS states (
            user_id TEXT PRIMARY KEY,
            state TEXT NOT NULL DEFAULT 'IDLE',
            data TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS messages_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            first_name TEXT,
            text TEXT,
            timestamp TEXT,
            type TEXT,
            direction TEXT
        );
        CREATE TABLE IF NOT EXISTS forward_map (
            message_id TEXT PRIMARY KEY,
            user_id INTEGER,
            first_name TEXT
        );
        CREATE TABLE IF NOT EXISTS registered_users (
            user_id TEXT PRIMARY KEY,
            first_name TEXT,
            phone TEXT,
            registered_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            response TEXT,
            keywords TEXT DEFAULT '[]',
            smart_enabled INTEGER DEFAULT 1,
            created_at TEXT,
            use_count INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS employers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            admin_id TEXT,
            description TEXT,
            code TEXT UNIQUE,
            created_at TEXT,
            active INTEGER DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_messages_user ON messages_log(user_id);
        CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages_log(timestamp);
    """)
    conn.commit()
    conn.close()

# ── States ──
def load_all_states():
    conn = get_conn()
    rows = conn.execute("SELECT user_id, state, data FROM states").fetchall()
    conn.close()
    states = {}
    data = {}
    for r in rows:
        states[r["user_id"]] = r["state"]
        try:
            data[r["user_id"]] = json.loads(r["data"])
        except (json.JSONDecodeError, TypeError):
            data[r["user_id"]] = {}
    return states, data

def save_state(user_id, state, data_dict):
    conn = get_conn()
    conn.execute(
        "INSERT INTO states (user_id, state, data) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET state=excluded.state, data=excluded.data",
        (str(user_id), state, json.dumps(data_dict, ensure_ascii=False))
    )
    conn.commit()
    conn.close()

def delete_state(user_id):
    conn = get_conn()
    conn.execute("DELETE FROM states WHERE user_id=?", (str(user_id),))
    conn.commit()
    conn.close()

# ── Registered Users ──
def load_all_registered():
    conn = get_conn()
    rows = conn.execute("SELECT user_id, first_name, phone, registered_at FROM registered_users").fetchall()
    conn.close()
    return {r["user_id"]: {"first_name": r["first_name"], "phone": r["phone"], "registered_at": r["registered_at"]} for r in rows}

def is_registered_db(user_id):
    conn = get_conn()
    r = conn.execute("SELECT 1 FROM registered_users WHERE user_id=?", (str(user_id),)).fetchone()
    conn.close()
    return r is not None

def register_user_db(user_id, first_name, phone, registered_at):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO registered_users (user_id, first_name, phone, registered_at) VALUES (?, ?, ?, ?)",
        (str(user_id), first_name, phone, registered_at)
    )
    conn.commit()
    conn.close()

def unregister_user_db(user_id):
    conn = get_conn()
    conn.execute("DELETE FROM registered_users WHERE user_id=?", (str(user_id),))
    conn.commit()
    conn.close()

# ── SOPs ──
def load_all_sops():
    conn = get_conn()
    rows = conn.execute("SELECT id, name, response, keywords, smart_enabled, created_at, use_count FROM sops ORDER BY id").fetchall()
    conn.close()
    result = []
    for r in rows:
        try:
            keywords = json.loads(r["keywords"]) if r["keywords"] else []
        except (json.JSONDecodeError, TypeError):
            keywords = []
        result.append({
            "id": r["id"],
            "name": r["name"],
            "response": r["response"],
            "keywords": keywords,
            "smart_enabled": bool(r["smart_enabled"]),
            "created_at": r["created_at"],
            "use_count": r["use_count"]
        })
    return result

def add_sop_db(name, response, keywords):
    import time
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO sops (name, response, keywords, created_at) VALUES (?, ?, ?, ?)",
        (name.strip(), response.strip(), json.dumps(keywords), time.strftime("%Y-%m-%d %H:%M:%S"))
    )
    sop_id = c.lastrowid
    conn.commit()
    conn.close()
    return sop_id

def update_sop_db(sop_id, name=None, response=None, keywords_str=None, smart_enabled=None):
    import time
    conn = get_conn()
    fields = []
    vals = []
    if name is not None:
        fields.append("name=?")
        vals.append(name.strip())
    if response is not None:
        fields.append("response=?")
        vals.append(response.strip())
    if keywords_str is not None:
        kws = [k.strip() for k in keywords_str.split(",") if k.strip()]
        fields.append("keywords=?")
        vals.append(json.dumps(kws))
    if smart_enabled is not None:
        fields.append("smart_enabled=?")
        vals.append(1 if smart_enabled else 0)
    if fields:
        vals.append(sop_id)
        conn.execute(f"UPDATE sops SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
    conn.close()

def delete_sop_db(sop_id):
    conn = get_conn()
    conn.execute("DELETE FROM sops WHERE id=?", (sop_id,))
    conn.commit()
    conn.close()

def increment_sop_use_count(sop_id):
    conn = get_conn()
    conn.execute("UPDATE sops SET use_count = use_count + 1 WHERE id=?", (sop_id,))
    conn.commit()
    conn.close()

# ── Employers ──
def load_all_employers():
    conn = get_conn()
    rows = conn.execute("SELECT id, name, admin_id, description, code, created_at, active FROM employers ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_employer_db(name, admin_id, description, code, created_at):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO employers (name, admin_id, description, code, created_at) VALUES (?, ?, ?, ?, ?)",
        (name.strip(), str(admin_id).strip(), description.strip(), code, created_at)
    )
    emp_id = c.lastrowid
    conn.commit()
    conn.close()
    return emp_id

def update_employer_db(emp_id, name=None, admin_id=None, description=None, active=None):
    conn = get_conn()
    fields = []
    vals = []
    if name is not None:
        fields.append("name=?")
        vals.append(name.strip())
    if admin_id is not None:
        fields.append("admin_id=?")
        vals.append(str(admin_id).strip())
    if description is not None:
        fields.append("description=?")
        vals.append(description.strip())
    if active is not None:
        fields.append("active=?")
        vals.append(1 if active else 0)
    if fields:
        vals.append(emp_id)
        conn.execute(f"UPDATE employers SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
    conn.close()

def delete_employer_db(emp_id):
    conn = get_conn()
    conn.execute("DELETE FROM employers WHERE id=?", (emp_id,))
    conn.commit()
    conn.close()

def update_employer_code(emp_id, code):
    conn = get_conn()
    conn.execute("UPDATE employers SET code=? WHERE id=?", (code, emp_id))
    conn.commit()
    conn.close()

# ── Forward Map ──
def load_all_forward_map():
    conn = get_conn()
    rows = conn.execute("SELECT message_id, user_id, first_name FROM forward_map").fetchall()
    conn.close()
    return {str(r["message_id"]): {"user_id": r["user_id"], "first_name": r["first_name"]} for r in rows}

def save_forward_map_entry(message_id, user_id, first_name):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO forward_map (message_id, user_id, first_name) VALUES (?, ?, ?)",
        (str(message_id), user_id, first_name)
    )
    conn.commit()
    conn.close()

# ── Messages Log ──
def log_message_db(user_id, first_name, text, timestamp, type_=None, direction=None):
    if not text or not text.strip():
        return
    conn = get_conn()
    conn.execute(
        "INSERT INTO messages_log (user_id, first_name, text, timestamp, type, direction) VALUES (?, ?, ?, ?, ?, ?)",
        (str(user_id), first_name, text.strip(), timestamp, type_, direction)
    )
    conn.commit()
    conn.close()

def get_all_messages_db(limit=200, offset=0):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, user_id, first_name, text, timestamp, type, direction FROM messages_log ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_conversation_db(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, user_id, first_name, text, timestamp, type, direction FROM messages_log WHERE user_id=? ORDER BY timestamp ASC",
        (str(user_id),)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_messages_in_date_range(start_iso, end_iso=None):
    conn = get_conn()
    if end_iso:
        rows = conn.execute(
            "SELECT id, user_id, first_name, text, timestamp, type, direction FROM messages_log WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp DESC",
            (start_iso, end_iso)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, user_id, first_name, text, timestamp, type, direction FROM messages_log WHERE timestamp >= ? ORDER BY timestamp DESC",
            (start_iso,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_messages_since(timestamp):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, user_id, first_name, text, timestamp, type, direction FROM messages_log WHERE timestamp >= ? ORDER BY timestamp ASC",
        (timestamp,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
