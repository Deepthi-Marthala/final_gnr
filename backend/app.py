from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.secret_key = 'gnr-secret'
CORS(app)

# ====================================================
# DATABASE SETUP
# ====================================================

if os.environ.get("DATABASE_URL"):
    import psycopg2
    from psycopg2.extras import RealDictCursor

    DATABASE_URL = os.environ.get("DATABASE_URL")

    def get_db():
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

    DB_TYPE = "postgres"
else:
    import sqlite3

    DB_PATH = os.path.join(os.path.dirname(__file__), 'gnr.db')

    def get_db():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    DB_TYPE = "sqlite"

print("🔥 USING DB:", DB_TYPE)

# ====================================================
# INIT DATABASE
# ====================================================

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # PRODUCTS TABLE
    if DB_TYPE == "postgres":
        cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT,
            category TEXT,
            price FLOAT,
            image TEXT
        )
        """)
    else:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            price REAL,
            image TEXT
        )
        """)

    # USERS TABLE ✅ NEW
    if DB_TYPE == "postgres":
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT
        )
        """)
    else:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT
        )
        """)

    conn.commit()
    cur.close()
    conn.close()

init_db()

# ====================================================
# PRODUCTS API
# ====================================================

@app.route('/api/products')
def get_products():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM products ORDER BY id DESC")

    if DB_TYPE == "postgres":
        data = cur.fetchall()
    else:
        data = [dict(row) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return jsonify(data)

# ====================================================
# REGISTER API ✅
# ====================================================

@app.route('/api/register', methods=['POST'])
def register():
    try:
        d = request.json
        name = d.get('name')
        email = d.get('email')
        password = d.get('password')

        conn = get_db()
        cur = conn.cursor()

        if DB_TYPE == "postgres":
            cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        else:
            cur.execute("SELECT * FROM users WHERE email=?", (email,))

        if cur.fetchone():
            return jsonify({"error": "User already exists"}), 400

        if DB_TYPE == "postgres":
            cur.execute(
                "INSERT INTO users (name,email,password) VALUES (%s,%s,%s)",
                (name, email, password)
            )
        else:
            cur.execute(
                "INSERT INTO users (name,email,password) VALUES (?,?,?)",
                (name, email, password)
            )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ====================================================
# LOGIN API ✅
# ====================================================

@app.route('/api/login', methods=['POST'])
def login():
    d = request.json
    email = d.get('email')
    password = d.get('password')

    conn = get_db()
    cur = conn.cursor()

    if DB_TYPE == "postgres":
        cur.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cur.fetchone()
    else:
        cur.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        row = cur.fetchone()
        user = dict(row) if row else None

    cur.close()
    conn.close()

    if user:
        return jsonify({"success": True, "name": user["name"], "email": user["email"]})
    else:
        return jsonify({"error": "Invalid credentials"}), 401

# ====================================================
# FRONTEND
# ====================================================

@app.route('/')
def home():
    return send_from_directory('../frontend', 'index.html')

@app.route('/<path:path>')
def serve(path):
    if path.startswith('api'):
        return jsonify({"error": "Not found"}), 404
    return send_from_directory('../frontend', path)

# ====================================================
# MAIN
# ====================================================

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)