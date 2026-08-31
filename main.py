
import os, hashlib, secrets, uuid
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

load_dotenv()
BASE=Path(__file__).resolve().parent
UP=BASE/"uploads"; UP.mkdir(exist_ok=True)
DATABASE_URL=os.getenv("DATABASE_URL","").strip()
ADMIN_MOBILE=os.getenv("ADMIN_MOBILE","").strip()
ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD","").strip()
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required for production V9")

app=FastAPI(title="AtoZ Toys & Keychain V9")

def db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def ph(x): return hashlib.sha256(x.encode()).hexdigest()

def init():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
          id BIGSERIAL PRIMARY KEY,name TEXT NOT NULL,mobile TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'customer',
          created_at TIMESTAMPTZ DEFAULT now())""")
        c.execute("""CREATE TABLE IF NOT EXISTS sessions(
          token TEXT PRIMARY KEY,user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
          created_at TIMESTAMPTZ DEFAULT now())""")
        c.execute("""CREATE TABLE IF NOT EXISTS products(
          id BIGSERIAL PRIMARY KEY,name TEXT NOT NULL,category TEXT NOT NULL,
          price INTEGER NOT NULL,old_price INTEGER,emoji TEXT DEFAULT '🧸',
          image_url TEXT DEFAULT '',stock INTEGER NOT NULL DEFAULT 0,
          description TEXT DEFAULT '',active BOOLEAN DEFAULT TRUE,
          created_at TIMESTAMPTZ DEFAULT now(),updated_at TIMESTAMPTZ DEFAULT now())""")
        c.execute("""CREATE TABLE IF NOT EXISTS images(
          id BIGSERIAL PRIMARY KEY,product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,
          path TEXT NOT NULL,created_at TIMESTAMPTZ DEFAULT now())""")
        c.execute("""CREATE TABLE IF NOT EXISTS orders(
          id BIGSERIAL PRIMARY KEY,user_id BIGINT REFERENCES users(id),
          customer_name TEXT NOT NULL,mobile TEXT NOT NULL,address TEXT NOT NULL,
          total INTEGER NOT NULL,payment_method TEXT NOT NULL DEFAULT 'COD',
          payment_status TEXT NOT NULL DEFAULT 'pending',
          order_status TEXT NOT NULL DEFAULT 'new',
          created_at TIMESTAMPTZ DEFAULT now())""")
        c.execute("""CREATE TABLE IF NOT EXISTS order_items(
          id BIGSERIAL PRIMARY KEY,order_id BIGINT REFERENCES orders(id) ON DELETE CASCADE,
          product_id BIGINT REFERENCES products(id),name TEXT NOT NULL,qty INTEGER NOT NULL,price INTEGER NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)""")
        defaults=[
          ("brand_name","AtoZ Toys & Keychain"),("hero_badge","🌈 PLAY • GIFT • SMILE"),
          ("hero_title","Big Smiles. Little Toys!"),("hero_text","Steel mini toys, colorful piggy banks, mini almirahs, keychains & cute gifts."),
          ("hero_button","Shop Now ✨"),("shop_title","Kids' Favorites ⭐"),("footer_text","AtoZ Toys & Keychain"),
          ("whatsapp",""),("support_text","Customer Support"),("free_shipping","Free Shipping on orders above ₹499"),
          ("cod_text","COD Available"),("returns_text","Easy Returns"),("secure_text","Secure Shopping")]
        for k,v in defaults:
            c.execute("INSERT INTO settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO NOTHING",(k,v))
        if c.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]==0 and ADMIN_MOBILE and ADMIN_PASSWORD:
            c.execute("INSERT INTO users(name,mobile,password_hash,role) VALUES(%s,%s,%s,'admin') ON CONFLICT(mobile) DO UPDATE SET role='admin'",("AtoZ Admin",ADMIN_MOBILE,ph(ADMIN_PASSWORD)))
        if c.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]==0:
            demo=[("Rainbow Piggy Bank","Piggy Banks",399,499,"🐷",30,"Colorful savings bank"),
                  ("Mini Steel Almirah","Mini Almirah",549,699,"🗄️",15,"Cute mini steel almirah"),
                  ("Fun Cartoon Keychain","Keychains",149,199,"🔑",50,"Cute keychain"),
                  ("Mini Car Toy","Toys",249,329,"🚗",35,"Colorful mini car")]
            for x in demo:
                c.execute("INSERT INTO products(name,category,price,old_price,emoji,stock,description) VALUES(%s,%s,%s,%s,%s,%s,%s)",x)

@app.on_event("startup")
def startup(): init()

def current(a:Optional[str]=Header(None)):
    if not a or not a.startswith("Bearer "): return None
    with db() as c:
        r=c.execute("SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=%s",(a[7:],)).fetchone()
        return r

def admin(u=Depends(current)):
    if not u or u["role"]!="admin": raise HTTPException(403,"Admin login required")
    return u

class Auth(BaseModel):
    name:str="Customer"; mobile:str; password:str
class Product(BaseModel):
    name:str; category:str; price:int; old_price:Optional[int]=None; emoji:str="🧸"
    image_url:str=""; stock:int=0; description:str=""
class Setting(BaseModel): key:str; value:str
class OrderItem(BaseModel): product_id:int; qty:int
class OrderIn(BaseModel):
    customer_name:str; mobile:str; address:str; payment_method:str="COD"; items:list[OrderItem]

@app.get("/api/health")
def health(): return {"ok":True,"service":"AtoZ Toys V9"}

@app.get("/api/settings")
def settings():
    with db() as c: return {x["key"]:x["value"] for x in c.execute("SELECT * FROM settings").fetchall()}

@app.get("/api/admin/settings")
def admin_settings(u=Depends(admin)): return settings()

@app.put("/api/admin/settings")
def save_setting(x:Setting,u=Depends(admin)):
    allowed={"brand_name","hero_badge","hero_title","hero_text","hero_button","shop_title","footer_text","whatsapp","support_text","free_shipping","cod_text","returns_text","secure_text"}
    if x.key not in allowed: raise HTTPException(400,"Invalid setting")
    with db() as c: c.execute("INSERT INTO settings VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(x.key,x.value))
    return {"ok":True}

@app.get("/api/products")
def products(q:Optional[str]=None,category:Optional[str]=None):
    with db() as c:
        sql="SELECT * FROM products WHERE active=TRUE"; args=[]
        if category and category!="All": sql+=" AND category=%s"; args.append(category)
        if q: sql+=" AND (name ILIKE %s OR category ILIKE %s)"; args += [f"%{q}%",f"%{q}%"]
        rows=[]
        for p in c.execute(sql+" ORDER BY id DESC",args).fetchall():
            p=dict(p); p["images"]=[x["path"] for x in c.execute("SELECT path FROM images WHERE product_id=%s ORDER BY id",(p["id"],)).fetchall()]
            rows.append(p)
        return rows

@app.post("/api/auth/login")
def login(a:Auth):
    with db() as c:
        r=c.execute("SELECT * FROM users WHERE mobile=%s AND password_hash=%s",(a.mobile,ph(a.password))).fetchone()
        if not r: raise HTTPException(401,"Invalid login")
        t=secrets.token_urlsafe(32); c.execute("INSERT INTO sessions(token,user_id) VALUES(%s,%s)",(t,r["id"]))
        return {"token":t,"user":r}

@app.post("/api/auth/register")
def register(a:Auth):
    with db() as c:
        try:
            r=c.execute("INSERT INTO users(name,mobile,password_hash) VALUES(%s,%s,%s) RETURNING *",(a.name,a.mobile,ph(a.password))).fetchone()
        except psycopg.errors.UniqueViolation: raise HTTPException(409,"Mobile already registered")
        t=secrets.token_urlsafe(32); c.execute("INSERT INTO sessions(token,user_id) VALUES(%s,%s)",(t,r["id"]))
        return {"token":t,"user":r}

@app.post("/api/admin/products")
def add_product(p:Product,u=Depends(admin)):
    with db() as c:
        return c.execute("""INSERT INTO products(name,category,price,old_price,emoji,image_url,stock,description)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",(p.name,p.category,p.price,p.old_price,p.emoji,p.image_url,p.stock,p.description)).fetchone()

@app.put("/api/admin/products/{pid}")
def edit_product(pid:int,p:Product,u=Depends(admin)):
    with db() as c:
        c.execute("""UPDATE products SET name=%s,category=%s,price=%s,old_price=%s,emoji=%s,image_url=%s,stock=%s,description=%s,updated_at=now() WHERE id=%s""",
                  (p.name,p.category,p.price,p.old_price,p.emoji,p.image_url,p.stock,p.description,pid))
    return {"ok":True}

@app.delete("/api/admin/products/{pid}")
def delete_product(pid:int,u=Depends(admin)):
    with db() as c: c.execute("UPDATE products SET active=FALSE,updated_at=now() WHERE id=%s",(pid,))
    return {"ok":True}

@app.post("/api/admin/products/{pid}/images")
async def upload(pid:int,files:list[UploadFile]=File(...),u=Depends(admin)):
    saved=[]
    with db() as c:
        if not c.execute("SELECT id FROM products WHERE id=%s",(pid,)).fetchone(): raise HTTPException(404,"Product not found")
        for f in files:
            if not f.content_type or not f.content_type.startswith("image/"): continue
            ext=Path(f.filename or ".jpg").suffix.lower()
            if ext not in {".jpg",".jpeg",".png",".webp"}: continue
            data=await f.read()
            if len(data)>8*1024*1024: continue
            name=uuid.uuid4().hex+ext; (UP/name).write_bytes(data); path="/uploads/"+name
            c.execute("INSERT INTO images(product_id,path) VALUES(%s,%s)",(pid,path)); saved.append(path)
    return {"images":saved}

@app.post("/api/orders")
def create_order(o:OrderIn,u=Depends(current)):
    if not o.items: raise HTTPException(400,"Cart is empty")
    with db() as c:
        total=0; rows=[]
        for it in o.items:
            p=c.execute("SELECT id,name,price,stock FROM products WHERE id=%s AND active=TRUE FOR UPDATE",(it.product_id,)).fetchone()
            if not p or it.qty<1 or p["stock"]<it.qty: raise HTTPException(400,"Product unavailable or insufficient stock")
            total += p["price"]*it.qty; rows.append((p,it.qty))
        uid=u["id"] if u else None
        order=c.execute("""INSERT INTO orders(user_id,customer_name,mobile,address,total,payment_method)
          VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""",(uid,o.customer_name,o.mobile,o.address,total,o.payment_method)).fetchone()
        oid=order["id"]
        for p,q in rows:
            c.execute("INSERT INTO order_items(order_id,product_id,name,qty,price) VALUES(%s,%s,%s,%s,%s)",(oid,p["id"],p["name"],q,p["price"]))
            c.execute("UPDATE products SET stock=stock-%s,updated_at=now() WHERE id=%s",(q,p["id"]))
        return {"ok":True,"order_id":oid,"total":total}

@app.get("/api/admin/orders")
def orders(u=Depends(admin)):
    with db() as c:
        return c.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 200").fetchall()

@app.get("/api/admin/stats")
def stats(u=Depends(admin)):
    with db() as c:
        return {"products":c.execute("SELECT COUNT(*) AS n FROM products WHERE active=TRUE").fetchone()["n"],
                "customers":c.execute("SELECT COUNT(*) AS n FROM users WHERE role='customer'").fetchone()["n"],
                "orders":c.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"],
                "revenue":c.execute("SELECT COALESCE(SUM(total),0) AS n FROM orders WHERE payment_status='paid' OR payment_method='COD'").fetchone()["n"]}

app.mount("/uploads",StaticFiles(directory=UP),name="uploads")
@app.get("/")
def home(): return FileResponse(BASE/"index.html")
