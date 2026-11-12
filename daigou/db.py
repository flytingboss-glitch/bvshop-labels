import os
import random
import sqlite3
import string

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL,
  name TEXT NOT NULL, phone TEXT DEFAULT '', member_code TEXT UNIQUE NOT NULL,
  is_admin INTEGER DEFAULT 0, credit_twd INTEGER DEFAULT 0,
  bal_twd INTEGER DEFAULT 0, bal_jpy INTEGER DEFAULT 0,
  created TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS announcements (
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT DEFAULT '',
  important INTEGER DEFAULT 0, created TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS articles (
  id INTEGER PRIMARY KEY, category TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL, body TEXT DEFAULT '', sort INTEGER DEFAULT 0,
  is_faq INTEGER DEFAULT 0, updated TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS purchases (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, url TEXT NOT NULL,
  title TEXT DEFAULT '', spec TEXT DEFAULT '', qty INTEGER DEFAULT 1,
  price_jpy INTEGER DEFAULT 0, jp_ship_jpy INTEGER DEFAULT 0,
  mode TEXT DEFAULT '網路採購', note TEXT DEFAULT '', status TEXT DEFAULT '待採購',
  admin_note TEXT DEFAULT '', created TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS parcels (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, carrier TEXT DEFAULT '',
  tracking TEXT DEFAULT '', content TEXT DEFAULT '', value_jpy INTEGER DEFAULT 0,
  weight REAL, status TEXT DEFAULT '預報中', purchase_id INTEGER,
  created TEXT DEFAULT (datetime('now','localtime')), received TEXT
);
CREATE TABLE IF NOT EXISTS shipments (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, recipient TEXT NOT NULL,
  phone TEXT NOT NULL, address TEXT NOT NULL, note TEXT DEFAULT '',
  weight REAL, fee_twd INTEGER, tracking TEXT DEFAULT '', status TEXT DEFAULT '待秤重',
  created TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS shipment_items (shipment_id INTEGER, parcel_id INTEGER);
CREATE TABLE IF NOT EXISTS bills (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, kind TEXT NOT NULL,
  currency TEXT NOT NULL, amount INTEGER NOT NULL, ref TEXT DEFAULT '',
  status TEXT DEFAULT '未付款', due TEXT, paid TEXT,
  created TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS topups (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, currency TEXT NOT NULL,
  amount INTEGER NOT NULL, account_last5 TEXT DEFAULT '', status TEXT DEFAULT '待確認',
  created TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS ledger (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, currency TEXT NOT NULL,
  amount INTEGER NOT NULL, memo TEXT DEFAULT '',
  created TEXT DEFAULT (datetime('now','localtime'))
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    os.makedirs(os.path.dirname(os.path.abspath(app.config["DATABASE"])), exist_ok=True)
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def new_member_code(db):
    while True:
        code = "JP" + "".join(random.choices(string.digits, k=6))
        if not db.execute("SELECT 1 FROM users WHERE member_code=?", (code,)).fetchone():
            return code


def get_setting(key, default=""):
    row = get_db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    db = get_db()
    db.execute("INSERT INTO settings(key,value) VALUES(?,?) "
               "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
    db.commit()
