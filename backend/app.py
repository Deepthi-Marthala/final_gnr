from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import os

app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.secret_key = 'gnr-secret'
CORS(app)

# ====================================================
# DATABASE SETUP (AUTO SWITCH)
# ====================================================

if os.environ.get("DATABASE_URL"):
    # 🔵 PRODUCTION (Render → PostgreSQL)
    import psycopg2
    from psycopg2.extras import RealDictCursor

    DATABASE_URL = os.environ.get("DATABASE_URL")

    def get_db():
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

    DB_TYPE = "postgres"

else:
    # 🟢 LOCAL (SQLite)
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

    if DB_TYPE == "postgres":
        cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT,
            category TEXT,
            price FLOAT,
            original_price FLOAT,
            discount INTEGER,
            image TEXT,
            description TEXT,
            sizes TEXT,
            is_new BOOLEAN DEFAULT TRUE,
            in_stock BOOLEAN DEFAULT TRUE
        )
        """)
    else:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            price REAL,
            original_price REAL,
            discount INTEGER,
            image TEXT,
            description TEXT,
            sizes TEXT,
            is_new INTEGER DEFAULT 1,
            in_stock INTEGER DEFAULT 1
        )
        """)

    # check data
    cur.execute("SELECT COUNT(*) FROM products")
    count = cur.fetchone()[0] if DB_TYPE == "sqlite" else cur.fetchone()['count']

    if count == 0:
        if DB_TYPE == "postgres":
            cur.executemany("""
            INSERT INTO products (name,category,price,original_price,discount,image)
            VALUES (%s,%s,%s,%s,%s,%s)
            """, [
                ('Crocs Clog', 'crocs', 799, 1299, 38,
                 'https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa'),

                ('Sports Shoes', 'shoes', 1499, 2499, 40,
                 'https://images.unsplash.com/photo-1542291026-7eec264c27ff'),

                ('Gold Chain', 'jewellery', 599, 999, 40,
                 'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338')
            ])
        else:
            cur.executemany("""
            INSERT INTO products (name,category,price,original_price,discount,image)
            VALUES (?,?,?,?,?,?)
            """, [
                ('Crocs Clog', 'crocs', 799, 1299, 38,
                 'https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa'),

                ('Sports Shoes', 'shoes', 1499, 2499, 40,
                 'https://images.unsplash.com/photo-1542291026-7eec264c27ff'),

                ('Gold Chain', 'jewellery', 599, 999, 40,
                 'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338')
            ])

    conn.commit()
    cur.close()
    conn.close()

# ✅ IMPORTANT
init_db()

# ====================================================
# PRODUCTS API
# ====================================================

@app.route('/api/products')
def get_products():
    try:
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

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ====================================================
# ADD PRODUCT
# ====================================================

@app.route('/api/products', methods=['POST'])
def add_product():
    d = request.json

    conn = get_db()
    cur = conn.cursor()

    if DB_TYPE == "postgres":
        cur.execute("""
        INSERT INTO products (name,category,price,image)
        VALUES (%s,%s,%s,%s) RETURNING *
        """, (d['name'], d['category'], d['price'], d['image']))
        product = cur.fetchone()
    else:
        cur.execute("""
        INSERT INTO products (name,category,price,image)
        VALUES (?,?,?,?)
        """, (d['name'], d['category'], d['price'], d['image']))
        conn.commit()
        cur.execute("SELECT * FROM products ORDER BY id DESC LIMIT 1")
        product = dict(cur.fetchone())

    conn.commit()
    cur.close()
    conn.close()

    return jsonify(product)

# ====================================================
# DELETE PRODUCT
# ====================================================

@app.route('/api/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    conn = get_db()
    cur = conn.cursor()

    if DB_TYPE == "postgres":
        cur.execute("DELETE FROM products WHERE id=%s", (id,))
    else:
        cur.execute("DELETE FROM products WHERE id=?", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"deleted": id})

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