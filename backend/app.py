from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import sqlite3, os, json

app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.secret_key = 'gnr-footwear-secret-2026'
CORS(app, supports_credentials=True)

DB_PATH = '/tmp/gnr.db' if os.environ.get('RENDER') else os.path.join(os.path.dirname(__file__), 'gnr.db')

OWNER_EMAIL    = 'owner@gnrfootwear.com'
OWNER_PASSWORD = 'gnr@owner2026'
WA_NUMBER      = '917337595239'

# ================================================================
#  DATABASE
# ================================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    conn.execute('''CREATE TABLE IF NOT EXISTS products (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        name           TEXT    NOT NULL,
        category       TEXT    NOT NULL,
        price          REAL    NOT NULL,
        original_price REAL    DEFAULT 0,
        discount       INTEGER DEFAULT 0,
        image          TEXT    DEFAULT '',
        description    TEXT    DEFAULT '',
        extra          TEXT    DEFAULT '',
        sizes          TEXT    DEFAULT '',
        is_new         INTEGER DEFAULT 1,
        in_stock       INTEGER DEFAULT 1,
        stock_qty      TEXT    DEFAULT '{}',
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # safe migration for older databases
    for col, definition in [
        ('stock_qty', "TEXT DEFAULT '{}'"),
    ]:
        try:
            conn.execute(f'ALTER TABLE products ADD COLUMN {col} {definition}')
            conn.commit()
        except Exception:
            pass

    conn.execute('''CREATE TABLE IF NOT EXISTS customers (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        email      TEXT UNIQUE NOT NULL,
        password   TEXT NOT NULL,
        name       TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS wishlist (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT NOT NULL,
        product_id INTEGER NOT NULL,
        UNIQUE(user_email, product_id)
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS stock_log (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id   INTEGER NOT NULL,
        product_name TEXT    NOT NULL,
        action       TEXT    NOT NULL,
        note         TEXT    DEFAULT '',
        sizes_info   TEXT    DEFAULT '',
        logged_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Seed only Crocs, Shoes (men), Jewellery — NO women's heels / girls slippers
    if conn.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0:
        conn.executemany(
            '''INSERT INTO products
               (name,category,price,original_price,discount,image,description,extra,sizes,is_new,in_stock)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            [
                ('Classic Crocs Clog', 'crocs', 799, 1299, 38,
                 'https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=400&q=80',
                 'Comfortable everyday crocs. Lightweight and water-resistant.',
                 'Free Delivery | Easy Exchange', '6,7,8,9,10,11', 1, 1),

                ('Flip Flop Slides', 'crocs', 499, 799, 37,
                 'https://images.unsplash.com/photo-1562183241-b937e95585b6?w=400&q=80',
                 'Soft padded flip flop slides. Ultra comfortable.',
                 'Free Delivery | Easy Exchange', '6,7,8,9,10,11', 0, 1),

                ('Chunky Sports Shoes', 'shoes', 1299, 2199, 41,
                 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400&q=80',
                 'Trendy chunky sneakers for men. Available in multiple colours.',
                 'Free Delivery | Easy Exchange', '6,7,8,9,10,11', 0, 1),

                ('Zoncaster Leather Shoes', 'shoes', 2800, 9999, 72,
                 'https://images.unsplash.com/photo-1614253429340-98120bd6d753?w=400&q=80',
                 '100% genuine leather brogue shoes. Premium quality.',
                 'Free Delivery | Easy Exchange', '6,7,8,9,10,11', 1, 1),

                ('Sports Running Shoes', 'shoes', 1599, 2999, 46,
                 'https://images.unsplash.com/photo-1608231387042-66d1773070a5?w=400&q=80',
                 'Lightweight running shoes with cushioned sole.',
                 'Free Delivery | Easy Exchange', '6,7,8,9,10,11', 1, 1),

                ('Gold Chain Necklace', 'jewellery', 649, 999, 35,
                 'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=400&q=80',
                 'Premium gold-plated chain necklace. Perfect for all occasions.',
                 'Packed safely | Easy Returns', '', 1, 1),

                ('Silver Earrings Set', 'jewellery', 349, 599, 41,
                 'https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?w=400&q=80',
                 'Trendy silver earring set — 3 pairs. Light and stylish.',
                 'Packed safely | Easy Returns', '', 0, 1),
            ]
        )

    conn.commit()
    conn.close()

# ================================================================
#  AUTH HELPERS
# ================================================================

def owner_logged_in():
    return session.get('is_owner') is True

def owner_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not owner_logged_in():
            return jsonify({'error': 'Owner login required'}), 401
        return fn(*args, **kwargs)
    return wrapper

# ================================================================
#  OWNER AUTH
# ================================================================

@app.route('/api/owner/login', methods=['POST'])
def owner_login():
    d = request.json or {}
    if d.get('email') == OWNER_EMAIL and d.get('password') == OWNER_PASSWORD:
        session['is_owner'] = True
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid owner credentials'}), 401

@app.route('/api/owner/logout', methods=['POST'])
def owner_logout():
    session.pop('is_owner', None)
    return jsonify({'success': True})

@app.route('/api/owner/check')
def owner_check():
    return jsonify({'logged_in': owner_logged_in()})

# ================================================================
#  PRODUCT CRUD  (owner only for write)
# ================================================================

@app.route('/api/products', methods=['GET'])
def get_products():
    cat       = request.args.get('category', '')
    search    = request.args.get('search', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    size      = request.args.get('size', '')
    conn   = get_db()
    query  = 'SELECT * FROM products WHERE 1=1'
    params = []
    if cat and cat != 'all':
        query += ' AND category=?'; params.append(cat)
    if search:
        query += ' AND name LIKE ?'; params.append(f'%{search}%')
    if min_price is not None:
        query += ' AND price>=?'; params.append(min_price)
    if max_price is not None:
        query += ' AND price<=?'; params.append(max_price)
    if size:
        query += " AND (sizes LIKE ? OR sizes='')"
        params.append(f'%{size}%')
    query += ' ORDER BY id DESC'
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/products', methods=['POST'])
@owner_required
def add_product():
    d = request.json or {}
    if not d.get('name') or not d.get('price'):
        return jsonify({'error': 'name and price required'}), 400
    # auto-calc discount if not provided
    price    = float(d['price'])
    orig     = float(d.get('original_price') or 0)
    discount = int(d.get('discount') or 0)
    if orig > price and discount == 0:
        discount = round((1 - price / orig) * 100)
    conn = get_db()
    cur = conn.execute(
        '''INSERT INTO products
           (name,category,price,original_price,discount,image,description,extra,sizes,is_new,in_stock)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
        (d['name'], d.get('category', 'crocs'), price, orig, discount,
         d.get('image', ''), d.get('description', ''), d.get('extra', ''),
         d.get('sizes', ''),
         1 if d.get('is_new', True) else 0,
         1 if d.get('in_stock', True) else 0)
    )
    conn.execute(
        "INSERT INTO stock_log (product_id, product_name, action, note) VALUES (?,?,?,?)",
        (cur.lastrowid, d['name'], 'Product Added', '')
    )
    conn.commit()
    row = conn.execute('SELECT * FROM products WHERE id=?', (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201

@app.route('/api/products/<int:pid>', methods=['PUT'])
@owner_required
def update_product(pid):
    d = request.json or {}
    price    = float(d.get('price', 0))
    orig     = float(d.get('original_price') or 0)
    discount = int(d.get('discount') or 0)
    if orig > price and discount == 0:
        discount = round((1 - price / orig) * 100)
    conn = get_db()
    conn.execute(
        '''UPDATE products SET name=?,category=?,price=?,original_price=?,
           discount=?,image=?,description=?,extra=?,sizes=?,is_new=?,in_stock=?
           WHERE id=?''',
        (d['name'], d.get('category', 'crocs'), price, orig, discount,
         d.get('image', ''), d.get('description', ''), d.get('extra', ''),
         d.get('sizes', ''),
         1 if d.get('is_new', True) else 0,
         1 if d.get('in_stock', True) else 0, pid)
    )
    conn.execute(
        "INSERT INTO stock_log (product_id, product_name, action, note) VALUES (?,?,?,?)",
        (pid, d['name'], 'Product Updated', '')
    )
    conn.commit()
    row = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    conn.close()
    return jsonify(dict(row) if row else {'error': 'not found'})

@app.route('/api/products/<int:pid>', methods=['DELETE'])
@owner_required
def delete_product(pid):
    conn = get_db()
    row = conn.execute('SELECT name FROM products WHERE id=?', (pid,)).fetchone()
    name = row['name'] if row else 'Unknown'
    conn.execute('DELETE FROM products WHERE id=?', (pid,))
    conn.execute(
        "INSERT INTO stock_log (product_id, product_name, action) VALUES (?,?,?)",
        (pid, name, 'Product Deleted')
    )
    conn.commit()
    conn.close()
    return jsonify({'deleted': pid})

# ================================================================
#  STOCK API
# ================================================================

@app.route('/api/products/<int:pid>/stock', methods=['POST'])
@owner_required
def update_stock(pid):
    d         = request.json or {}
    stock_qty = d.get('stock_qty', {})
    note      = d.get('note', '')
    action    = d.get('action', 'Stock Updated')
    total     = sum(int(v) for v in stock_qty.values() if str(v).isdigit())
    in_stock  = 1 if total > 0 else 0
    conn = get_db()
    conn.execute(
        "UPDATE products SET stock_qty=?, in_stock=? WHERE id=?",
        (json.dumps(stock_qty), in_stock, pid)
    )
    row        = conn.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    sizes_info = ', '.join(f"Sz {k}: {v}" for k, v in stock_qty.items() if int(v or 0) > 0)
    conn.execute(
        "INSERT INTO stock_log (product_id, product_name, action, note, sizes_info) VALUES (?,?,?,?,?)",
        (pid, row['name'] if row else '', action, note, sizes_info)
    )
    conn.commit()
    conn.close()
    return jsonify(dict(row) if row else {'error': 'not found'})

@app.route('/api/stock-log')
@owner_required
def stock_log_api():
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM stock_log ORDER BY logged_at DESC LIMIT 100'
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/stats')
def stats():
    conn    = get_db()
    total   = conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    instock = conn.execute('SELECT COUNT(*) FROM products WHERE in_stock=1').fetchone()[0]
    conn.close()
    return jsonify({'total': total, 'in_stock': instock, 'out_of_stock': total - instock})

# ================================================================
#  CUSTOMER AUTH
# ================================================================

@app.route('/api/register', methods=['POST'])
def register():
    d = request.json or {}
    if not d.get('email') or not d.get('password'):
        return jsonify({'error': 'Email and password required'}), 400
    conn = get_db()
    try:
        conn.execute('INSERT INTO customers (email,password,name) VALUES (?,?,?)',
                     (d['email'], d['password'], d.get('name', '')))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'email': d['email']})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Email already registered'}), 409

@app.route('/api/login', methods=['POST'])
def login():
    d   = request.json or {}
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM customers WHERE email=? AND password=?',
        (d.get('email', ''), d.get('password', ''))
    ).fetchone()
    conn.close()
    if row:
        return jsonify({'success': True, 'email': row['email'], 'name': row['name']})
    return jsonify({'error': 'Invalid email or password'}), 401

# ================================================================
#  WISHLIST
# ================================================================

@app.route('/api/wishlist/<email>', methods=['GET'])
def get_wishlist(email):
    conn = get_db()
    rows = conn.execute(
        'SELECT p.* FROM products p JOIN wishlist w ON p.id=w.product_id WHERE w.user_email=?',
        (email,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/wishlist', methods=['POST'])
def toggle_wishlist():
    d     = request.json or {}
    email = d.get('email')
    pid   = d.get('product_id')
    if not email or not pid:
        return jsonify({'error': 'email and product_id required'}), 400
    conn   = get_db()
    exists = conn.execute(
        'SELECT id FROM wishlist WHERE user_email=? AND product_id=?', (email, pid)
    ).fetchone()
    if exists:
        conn.execute('DELETE FROM wishlist WHERE user_email=? AND product_id=?', (email, pid))
        conn.commit(); conn.close()
        return jsonify({'action': 'removed'})
    conn.execute('INSERT INTO wishlist (user_email,product_id) VALUES (?,?)', (email, pid))
    conn.commit(); conn.close()
    return jsonify({'action': 'added'})

# ================================================================
#  SERVE FRONTEND FILES
# ================================================================

@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/owner')
@app.route('/owner/')
def owner_portal():
    return send_from_directory('../frontend', 'owner.html')

@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('api/'):
        return jsonify({'error': 'Not found'}), 404
    try:
        return send_from_directory('../frontend', path)
    except Exception:
        return send_from_directory('../frontend', 'index.html')

# ================================================================
#  MAIN
# ================================================================

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    print(f"\n  GNR Footwear running on http://127.0.0.1:{port}")
    print(f"  Owner portal:  http://127.0.0.1:{port}/owner\n")
    app.run(debug=False, port=port, host='0.0.0.0')
