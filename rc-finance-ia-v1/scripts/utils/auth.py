from passlib.context import CryptContext
import streamlit as st
import sqlite3

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_db_connection():
    conn = sqlite3.connect("data/finance.db")
    conn.row_factory = sqlite3.Row
    return conn

def get_user(conn, email: str):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    return user

def get_current_user():
    if "user_id" not in st.session_state or st.session_state["user_id"] is None:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (st.session_state["user_id"],))
    user = cursor.fetchone()
    conn.close()
    return user

def authenticate_user(conn, email, password):
    user = get_user(conn, email)
    if user and verify_password(password, user["password_hash"]):
        return user
    return None

def create_user(conn, name: str, email: str, password: str, role: str = "member", active: int = 1) -> int:
    cursor = conn.cursor()
    password_hash = hash_password(password)
    cursor.execute(
        "INSERT INTO users (name, email, password_hash, role, active) VALUES (?, ?, ?, ?, ?)",
        (name, email, password_hash, role, active)
    )
    conn.commit()
    return cursor.lastrowid




ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASS = "Admin@123"

def ensure_default_admin(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT UNIQUE,
            password_hash TEXT,
            role TEXT DEFAULT 'member',
            active INTEGER DEFAULT 1
        )
        """
    )
    conn.commit()

    if not get_user(conn, ADMIN_EMAIL):
        create_user(conn, "Admin", ADMIN_EMAIL, ADMIN_PASS, "admin", 1)
        conn.commit()




def is_logged_in():
    """Verifica se o usuário está logado"""
    return st.session_state.get("logged_in", False) and st.session_state.get("user_id") is not None

