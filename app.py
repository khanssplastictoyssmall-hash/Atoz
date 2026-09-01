import os, json
from flask import Flask, request, jsonify, send_from_directory, session
import psycopg

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

DEFAULT_SETTINGS = {
    "store_name": "AtoZ Toys",
    "tagline": "Big Smiles. Little Toys!",
    "logo": "🧸",
    "phone": "+91 00000 00000",
    "email": "hello@atoztoys.example",
    "address": "Your city, India",
    "facebook": "",
    "instagram": "",
    "youtube": "",
    "footer_about": "Fun, colorful and gift-ready toys, keychains, piggy banks and mini collectibles.",
    "copyright": "© 2026 AtoZ Toys. All rights reserved."
}
DEFAULT_CATEGORIES = [
    ("Toys", None, "🧸"),
    ("Remote Control Toys", 1, "🚗"),
    ("Soft Toys", 1, "🐻"),
    ("Educational Toys", 1, "🧠"),
    ("Keychains", None, "🔑"),
    ("Piggy Banks", None, "🐷"),
    ("Mini Almirahs", None, "🗄️"),
    ("Gifts", None, "🎁"),
]
DEFAULT_PRODUCTS = [
    ("Mini Red Car", 249, "Toys", "https://images.unsplash.com/photo-1594787318286-3d835c1d207f?auto=format&fit=crop&w=800&q=80", "Bright mini toy car for fun gifting.", 1),
    ("Cute Teddy Bear", 399, "Soft Toys", "https://images.unsplash.com/photo-1559454403-82f2d14fbdce?auto=format&fit=crop&w=800&q=80", "Soft and cuddly teddy.", 1),
    ("Animal Keychain", 149, "Keychains", "https://images.unsplash.com/photo-1581235720704-06d3acfcb36f?auto=format&fit=crop&w=800&q=80", "Colorful collectible keychain.", 1),
]
DEFAULT_ADS = [
    ("Main Hero", "Big Smiles. Little Toys!", "Shop colorful toys & gifts", "Shop Now", "", 1),
    ("Sale Banner", "Weekend Toy Sale", "Fun picks at special prices", "Explore Deals", "", 2),
    ("Category Poster", "New Arrivals", "Fresh toys added regularly", "See New", "", 3),
    ("Trust Banner", "Easy Shopping", "Fast support • secure checkout • order tracking", "Learn More", "", 4),
    ("Gift Banner", "Gift Something Fun", "Perfect picks for birthdays & surprises", "Shop Gifts", "", 5),
]

def db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required for production")
    return psycopg.connect(DATABASE_URL, autocommit=True)

def init_db():
    """Create the schema and safely add columns required by this app.

    CREATE TABLE IF NOT EXISTS does NOT change an already-existing table.
    The ALTER TABLE statements below are therefore important when an older
    version of this app used the same PostgreSQL database.
    """
    with db() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INT PRIMARY KEY,
                data JSONB NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                parent_id INT REFERENCES categories(id) ON DELETE SET NULL,
                icon TEXT DEFAULT '🧸',
                sort_order INT DEFAULT 0
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                price NUMERIC(12,2) NOT NULL DEFAULT 0,
                category TEXT NOT NULL,
                image TEXT DEFAULT '',
                description TEXT DEFAULT '',
                stock INT DEFAULT 0,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS ads (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                headline TEXT DEFAULT '',
                text TEXT DEFAULT '',
                button TEXT DEFAULT 'Shop Now',
                image TEXT DEFAULT '',
                sort_order INT DEFAULT 0,
                active BOOLEAN DEFAULT TRUE
            )
        """)

        # IMPORTANT: if these tables already existed from an older version,
        # CREATE TABLE IF NOT EXISTS above does not add newly introduced columns.
        c.execute("ALTER TABLE settings ADD COLUMN IF NOT EXISTS data JSONB")
        c.execute("ALTER TABLE categories ADD COLUMN IF NOT EXISTS parent_id INT")
        c.execute("ALTER TABLE categories ADD COLUMN IF NOT EXISTS icon TEXT DEFAULT '🧸'")
        c.execute("ALTER TABLE categories ADD COLUMN IF NOT EXISTS sort_order INT DEFAULT 0")
        c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS price NUMERIC(12,2) DEFAULT 0")
        c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'Toys'")
        c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS image TEXT DEFAULT ''")
        c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS description TEXT DEFAULT ''")
        c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS stock INT DEFAULT 0")
        c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE")
        c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()")
        c.execute("ALTER TABLE ads ADD COLUMN IF NOT EXISTS title TEXT DEFAULT 'Banner'")
        c.execute("ALTER TABLE ads ADD COLUMN IF NOT EXISTS headline TEXT DEFAULT ''")
        c.execute("ALTER TABLE ads ADD COLUMN IF NOT EXISTS text TEXT DEFAULT ''")
        c.execute("ALTER TABLE ads ADD COLUMN IF NOT EXISTS button TEXT DEFAULT 'Shop Now'")
        c.execute("ALTER TABLE ads ADD COLUMN IF NOT EXISTS image TEXT DEFAULT ''")
        c.execute("ALTER TABLE ads ADD COLUMN IF NOT EXISTS sort_order INT DEFAULT 0")
        c.execute("ALTER TABLE ads ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE")

        # Repair NULLs that could prevent inserts/reads after a migration.
        c.execute("UPDATE settings SET data=%s WHERE id=1 AND data IS NULL", (json.dumps(DEFAULT_SETTINGS),))
        c.execute("UPDATE categories SET icon='🧸' WHERE icon IS NULL")
        c.execute("UPDATE categories SET sort_order=0 WHERE sort_order IS NULL")
        c.execute("UPDATE products SET price=0 WHERE price IS NULL")
        c.execute("UPDATE products SET category='Toys' WHERE category IS NULL")
        c.execute("UPDATE products SET image='' WHERE image IS NULL")
        c.execute("UPDATE products SET description='' WHERE description IS NULL")
        c.execute("UPDATE products SET stock=0 WHERE stock IS NULL")
        c.execute("UPDATE products SET active=TRUE WHERE active IS NULL")
        c.execute("UPDATE ads SET title='Banner' WHERE title IS NULL")
        c.execute("UPDATE ads SET headline='' WHERE headline IS NULL")
        c.execute("UPDATE ads SET text='' WHERE text IS NULL")
        c.execute("UPDATE ads SET button='Shop Now' WHERE button IS NULL")
        c.execute("UPDATE ads SET image='' WHERE image IS NULL")
        c.execute("UPDATE ads SET sort_order=0 WHERE sort_order IS NULL")
        c.execute("UPDATE ads SET active=TRUE WHERE active IS NULL")

        if c.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0:
            c.execute(
                "INSERT INTO settings(id,data) VALUES(1,%s)",
                (json.dumps(DEFAULT_SETTINGS),)
            )

        if c.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            ids = {}
            for name, parent, icon in DEFAULT_CATEGORIES:
                parent_id = ids.get("Toys") if parent == 1 else None
                row = c.execute(
                    "INSERT INTO categories(name,parent_id,icon,sort_order) "
                    "VALUES(%s,%s,%s,%s) RETURNING id",
                    (name, parent_id, icon, 0)
                ).fetchone()
                ids[name] = row[0]

        if c.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            for p in DEFAULT_PRODUCTS:
                c.execute(
                    "INSERT INTO products(name,price,category,image,description,stock) "
                    "VALUES(%s,%s,%s,%s,%s,%s)",
                    p
                )

        if c.execute("SELECT COUNT(*) FROM ads").fetchone()[0] == 0:
            for a in DEFAULT_ADS:
                c.execute(
                    "INSERT INTO ads(title,headline,text,button,image,sort_order) "
                    "VALUES(%s,%s,%s,%s,%s,%s)",
                    a
                )

@app.before_request
def startup():
    if request.path.startswith("/api/") or request.path in ("/", "/admin"):
        try: init_db()
        except Exception as e:
            if request.path.startswith("/api/"): return jsonify(error=str(e)), 500

def admin_required():
    return session.get("admin") is True

@app.get("/")
def home(): return send_from_directory(".", "index.html")

@app.get("/admin")
def admin(): return send_from_directory(".", "admin.html")

# Serve the frontend assets from the repository root.
@app.get("/styles.css")
def styles(): return send_from_directory(".", "styles.css", mimetype="text/css")

@app.get("/app.js")
def app_js(): return send_from_directory(".", "app.js", mimetype="application/javascript")

@app.get("/admin.js")
def admin_js(): return send_from_directory(".", "admin.js", mimetype="application/javascript")

@app.get("/api/store")
def store():
    with db() as c:
        s = c.execute("SELECT data FROM settings WHERE id=1").fetchone()[0]
        cats = [dict(zip(["id","name","parent_id","icon","sort_order"], r)) for r in c.execute("SELECT id,name,parent_id,icon,sort_order FROM categories ORDER BY sort_order,id").fetchall()]
        prods = [dict(zip(["id","name","price","category","image","description","stock","active"], r)) for r in c.execute("SELECT id,name,price,category,image,description,stock,active FROM products WHERE active=true ORDER BY id DESC").fetchall()]
        ads = [dict(zip(["id","title","headline","text","button","image","sort_order","active"], r)) for r in c.execute("SELECT id,title,headline,text,button,image,sort_order,active FROM ads WHERE active=true ORDER BY sort_order,id").fetchall()]
    return jsonify(settings=s, categories=cats, products=prods, ads=ads)

@app.post("/api/admin/login")
def login():
    data=request.get_json() or {}
    user=os.environ.get("ADMIN_USER","admin")
    pwd=os.environ.get("ADMIN_PASSWORD","change-me-now")
    if data.get("username")==user and data.get("password")==pwd:
        session["admin"]=True
        return jsonify(ok=True)
    return jsonify(error="Invalid admin login"), 401

@app.post("/api/admin/logout")
def logout(): session.clear(); return jsonify(ok=True)

@app.get("/api/admin/all")
def admin_all():
    if not admin_required(): return jsonify(error="Unauthorized"),401
    with db() as c:
        s=c.execute("SELECT data FROM settings WHERE id=1").fetchone()[0]
        cats=[dict(zip(["id","name","parent_id","icon","sort_order"],r)) for r in c.execute("SELECT id,name,parent_id,icon,sort_order FROM categories ORDER BY sort_order,id")]
        prods=[dict(zip(["id","name","price","category","image","description","stock","active"],r)) for r in c.execute("SELECT id,name,price,category,image,description,stock,active FROM products ORDER BY id DESC")]
        ads=[dict(zip(["id","title","headline","text","button","image","sort_order","active"],r)) for r in c.execute("SELECT id,title,headline,text,button,image,sort_order,active FROM ads ORDER BY sort_order,id")]
    return jsonify(settings=s,categories=cats,products=prods,ads=ads)

@app.put("/api/admin/settings")
def settings():
    if not admin_required(): return jsonify(error="Unauthorized"),401
    data=request.get_json() or {}
    with db() as c: c.execute("UPDATE settings SET data=%s WHERE id=1",(json.dumps(data),))
    return jsonify(ok=True)

@app.route("/api/admin/categories", methods=["POST","PUT","DELETE"])
def categories():
    if not admin_required(): return jsonify(error="Unauthorized"),401
    d=request.get_json() or {}
    with db() as c:
        if request.method=="POST":
            r=c.execute("INSERT INTO categories(name,parent_id,icon,sort_order) VALUES(%s,%s,%s,%s) RETURNING id",
                        (d.get("name"),d.get("parent_id"),d.get("icon","🧸"),d.get("sort_order",0))).fetchone()
            return jsonify(id=r[0])
        if request.method=="PUT":
            c.execute("UPDATE categories SET name=%s,parent_id=%s,icon=%s,sort_order=%s WHERE id=%s",
                      (d.get("name"),d.get("parent_id"),d.get("icon","🧸"),d.get("sort_order",0),d["id"]))
        else: c.execute("DELETE FROM categories WHERE id=%s",(d["id"],))
    return jsonify(ok=True)

@app.route("/api/admin/products", methods=["POST","PUT","DELETE"])
def products():
    if not admin_required(): return jsonify(error="Unauthorized"),401
    d=request.get_json() or {}
    with db() as c:
        if request.method=="POST":
            r=c.execute("""INSERT INTO products(name,price,category,image,description,stock,active)
                           VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (d["name"],d.get("price",0),d.get("category","Toys"),d.get("image",""),d.get("description",""),d.get("stock",0),d.get("active",True))).fetchone()
            return jsonify(id=r[0])
        if request.method=="PUT":
            c.execute("""UPDATE products SET name=%s,price=%s,category=%s,image=%s,description=%s,stock=%s,active=%s WHERE id=%s""",
                      (d["name"],d.get("price",0),d.get("category","Toys"),d.get("image",""),d.get("description",""),d.get("stock",0),d.get("active",True),d["id"]))
        else: c.execute("DELETE FROM products WHERE id=%s",(d["id"],))
    return jsonify(ok=True)

@app.route("/api/admin/ads", methods=["POST","PUT","DELETE"])
def ads():
    if not admin_required(): return jsonify(error="Unauthorized"),401
    d=request.get_json() or {}
    with db() as c:
        if request.method=="POST":
            r=c.execute("""INSERT INTO ads(title,headline,text,button,image,sort_order,active)
                           VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (d.get("title","Banner"),d.get("headline",""),d.get("text",""),d.get("button","Shop Now"),d.get("image",""),d.get("sort_order",0),d.get("active",True))).fetchone()
            return jsonify(id=r[0])
        if request.method=="PUT":
            c.execute("""UPDATE ads SET title=%s,headline=%s,text=%s,button=%s,image=%s,sort_order=%s,active=%s WHERE id=%s""",
                      (d.get("title","Banner"),d.get("headline",""),d.get("text",""),d.get("button","Shop Now"),d.get("image",""),d.get("sort_order",0),d.get("active",True),d["id"]))
        else: c.execute("DELETE FROM ads WHERE id=%s",(d["id"],))
    return jsonify(ok=True)

@app.get("/health")
def health(): return "OK"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
