from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.secret_key = 'gnr-secret'
CORS(app)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# ================= DB INIT =================
def init_db():
    conn = get_db()
    cur = conn.cursor()

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

    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()['count'] == 0:
        cur.executemany("""
        INSERT INTO products (name, category, price, original_price, discount, image)
        VALUES (%s,%s,%s,%s,%s,%s)
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

init_db()

# ================= API =================
@app.route('/api/products')
def get_products():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products ORDER BY id DESC")
    data = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(data)

@app.route('/api/products', methods=['POST'])
def add_product():
    d = request.json
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO products (name,category,price,image)
    VALUES (%s,%s,%s,%s) RETURNING *
    """, (d['name'], d['category'], d['price'], d['image']))

    product = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(product)

@app.route('/api/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id=%s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"deleted": id})

# ================= FRONTEND =================
@app.route('/')
def home():
    return send_from_directory('../frontend', 'index.html')

@app.route('/<path:path>')
def serve(path):
    if path.startswith('api'):
        return jsonify({"error": "Not found"}), 404
    return send_from_directory('../frontend', path)

# ================= MAIN =================
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)