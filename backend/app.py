from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import sqlite3, os, json

app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.secret_key = 'gnr-footwear-secret-2026'
CORS(app, supports_credentials=True)

DB_PATH = '/tmp/gnr.db' if os.environ.get('RENDER') else os.path.join(os.path.dirname(__file__), 'gnr.db')

OWNER_EMAIL    = 'owner@gnrfootwear.com'
OWNER_PASSWORD = 'gnr@owner2026'

# ================================================================
# DATABASE
# ================================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    conn.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        category TEXT,
        price REAL,
        original_price REAL,
        discount INTEGER,
        image TEXT,
        description TEXT,
        extra TEXT,
        sizes TEXT,
        is_new INTEGER,
        in_stock INTEGER,
        stock_qty TEXT DEFAULT '{}'
    )''')

    if conn.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0:
        conn.executemany('''
            INSERT INTO products (name,category,price,original_price,discount,image,description,extra,sizes,is_new,in_stock)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ''', [
            ('Classic Crocs Clog', 'crocs', 799, 1299, 38,
             'https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=400',
             'Comfortable everyday crocs', '', '6,7,8,9', 1, 1),

            ('Sports Shoes', 'shoes', 1499, 2499, 40,
             'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400',
             'Running shoes', '', '6,7,8,9', 1, 1),

            ('Gold Chain', 'jewellery', 599, 999, 40,
             'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=400',
             'Stylish chain', '', '', 1, 1)
        ])

    conn.commit()
    conn.close()

# ✅ IMPORTANT: RUN DB INIT ALWAYS (FIX)
init_db()

# ================================================================
# PRODUCTS API
# ================================================================

@app.route('/api/products')
def get_products():
    conn = get_db()
    rows = conn.execute('SELECT * FROM products ORDER BY id DESC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# ================================================================
# OWNER LOGIN
# ================================================================

@app.route('/api/owner/login', methods=['POST'])
def owner_login():
    d = request.json or {}
    if d.get('email') == OWNER_EMAIL and d.get('password') == OWNER_PASSWORD:
        session['is_owner'] = True
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid credentials'}), 401

# ================================================================
# FRONTEND SERVING
# ================================================================

@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('api/'):
        return jsonify({'error': 'Not found'}), 404
    try:
        return send_from_directory('../frontend', path)
    except:
        return send_from_directory('../frontend', 'index.html')

# ================================================================
# MAIN
# ================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)