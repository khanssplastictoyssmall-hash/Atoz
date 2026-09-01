import os, hashlib, secrets, base64, mimetypes
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
import psycopg
from psycopg.rows import dict_row

DATABASE_URL=os.getenv('DATABASE_URL','').strip()
ADMIN_MOBILE=os.getenv('ADMIN_MOBILE','').strip()
ADMIN_PASSWORD=os.getenv('ADMIN_PASSWORD','').strip()
if not DATABASE_URL: raise RuntimeError('DATABASE_URL is required for production')
app=FastAPI(title='Atoztoys Advanced V11')

def db(): return psycopg.connect(DATABASE_URL,row_factory=dict_row)
def ph(x): return hashlib.sha256(x.encode()).hexdigest()
def auth_user(a:Optional[str]):
    if not a or not a.startswith('Bearer '): return None
    with db() as c: return c.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=%s',(a[7:],)).fetchone()
def current(authorization:Optional[str]=Header(None)): return auth_user(authorization)
def admin(u=Depends(current)):
    if not u or u['role']!='admin': raise HTTPException(403,'Admin login required')
    return u

SCHEMA='''
CREATE TABLE IF NOT EXISTS users(id BIGSERIAL PRIMARY KEY,name TEXT NOT NULL,mobile TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'customer',created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS categories(id BIGSERIAL PRIMARY KEY,parent_id BIGINT REFERENCES categories(id) ON DELETE CASCADE,name TEXT NOT NULL,description TEXT DEFAULT '',image_url TEXT DEFAULT '',sort_order INT DEFAULT 0,active BOOLEAN DEFAULT TRUE);
CREATE TABLE IF NOT EXISTS products(id BIGSERIAL PRIMARY KEY,category_id BIGINT REFERENCES categories(id) ON DELETE SET NULL,name TEXT NOT NULL,price INT NOT NULL,old_price INT,sku TEXT DEFAULT '',emoji TEXT DEFAULT '🧸',description TEXT DEFAULT '',stock INT DEFAULT 0,image_url TEXT DEFAULT '',active BOOLEAN DEFAULT TRUE,created_at TIMESTAMPTZ DEFAULT now(),updated_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS product_images(id BIGSERIAL PRIMARY KEY,product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,data BYTEA NOT NULL,mime TEXT NOT NULL,created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS media(id BIGSERIAL PRIMARY KEY,kind TEXT NOT NULL,data BYTEA NOT NULL,mime TEXT NOT NULL,created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ads(id BIGSERIAL PRIMARY KEY,title TEXT NOT NULL,subtitle TEXT DEFAULT '',image_url TEXT DEFAULT '',link TEXT DEFAULT '',position TEXT DEFAULT 'hero',active BOOLEAN DEFAULT TRUE,sort_order INT DEFAULT 0);
CREATE TABLE IF NOT EXISTS orders(id BIGSERIAL PRIMARY KEY,user_id BIGINT REFERENCES users(id),customer_name TEXT NOT NULL,mobile TEXT NOT NULL,address TEXT NOT NULL,total INT NOT NULL,payment_method TEXT DEFAULT 'COD',payment_status TEXT DEFAULT 'pending',order_status TEXT DEFAULT 'new',created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS order_items(id BIGSERIAL PRIMARY KEY,order_id BIGINT REFERENCES orders(id) ON DELETE CASCADE,product_id BIGINT REFERENCES products(id),name TEXT NOT NULL,qty INT NOT NULL,price INT NOT NULL);
'''
DEFAULTS={'brand_name':'Atoztoys','tagline':'Play • Gift • Smile','hero_title':'Little Toys. Big Adventures.','hero_text':'Steel mini toys, piggy banks, mini almirahs, keychains and fun gifts for every little smile.','hero_button':'Explore Toys ✨','primary_color':'#6c2cff','accent_color':'#ff3f9d','footer_text':'Atoztoys — Colorful little things, big happiness.','whatsapp':'','shipping_text':'Free shipping above ₹499','cod_text':'Cash on Delivery available','support_text':'Fast support & easy shopping','logo_url':'','nav_cart_text':'Cart','login_text':'Account','category_title':'Explore Categories ✨','shop_title':'Trending Toys ⭐','admin_title':'Atoztoys Control Center','add_product_text':'Add Product','product_empty_text':'No products found.','cart_title':'Your Cart','checkout_text':'Checkout','buy_now_text':'Buy Now','add_cart_text':'Add to Cart 🛒','footer_text':'Atoztoys — Colorful little things, big happiness.'}

def init():
    with db() as c:
        for stmt in SCHEMA.split(';'):
            if stmt.strip(): c.execute(stmt)
        for k,v in DEFAULTS.items(): c.execute('INSERT INTO settings(key,value) VALUES(%s,%s) ON CONFLICT(key) DO NOTHING',(k,v))
        if ADMIN_MOBILE and ADMIN_PASSWORD:
            c.execute("INSERT INTO users(name,mobile,password_hash,role) VALUES('Atoztoys Admin',%s,%s,'admin') ON CONFLICT(mobile) DO UPDATE SET password_hash=EXCLUDED.password_hash,role='admin'",(ADMIN_MOBILE,ph(ADMIN_PASSWORD)))
        if c.execute('SELECT count(*) AS n FROM categories').fetchone()['n']==0:
            roots=[('Toys','Fun & colorful toys','🧸'),('Piggy Banks','Cute savings banks','🐷'),('Mini Almirah','Mini steel almirahs','🗄️'),('Keychains','Cute keychains','🔑'),('Gifts','Gift ideas for everyone','🎁')]
            for i,(n,d,e) in enumerate(roots): c.execute('INSERT INTO categories(parent_id,name,description,image_url,sort_order) VALUES(NULL,%s,%s,%s,%s)',(n,d,e,i))
        if c.execute('SELECT count(*) AS n FROM products').fetchone()['n']==0:
            cats={r['name']:r['id'] for r in c.execute('SELECT id,name FROM categories WHERE parent_id IS NULL').fetchall()}
            demo=[('Rainbow Piggy Bank','Piggy Banks',399,499,'🐷','Colorful savings bank',30),('Mini Steel Almirah','Mini Almirah',549,699,'🗄️','Cute mini steel almirah',15),('Fun Cartoon Keychain','Keychains',149,199,'🔑','Cute everyday keychain',50),('Mini Car Toy','Toys',249,329,'🚗','Colorful mini car toy',35)]
            for n,cat,p,op,e,d,s in demo: c.execute('INSERT INTO products(category_id,name,price,old_price,emoji,description,stock) VALUES(%s,%s,%s,%s,%s,%s,%s)',(cats.get(cat) or cats.get('Toys'),n,p,op,e,d,s))

@app.on_event('startup')
def startup(): init()

class Auth(BaseModel): name:str='Customer'; mobile:str; password:str
class CategoryIn(BaseModel): parent_id:Optional[int]=None; name:str; description:str=''; image_url:str=''; sort_order:int=0
class ProductIn(BaseModel): category_id:Optional[int]=None; name:str; price:int=0; old_price:Optional[int]=None; sku:str=''; emoji:str='🧸'; description:str=''; stock:int=0; image_url:str=''
class SettingIn(BaseModel): key:str; value:str
class AdIn(BaseModel): title:str; subtitle:str=''; image_url:str=''; link:str=''; position:str='hero'; active:bool=True; sort_order:int=0
class Item(BaseModel): product_id:int; qty:int=Field(gt=0)
class OrderIn(BaseModel): customer_name:str; mobile:str; address:str; payment_method:str='COD'; items:list[Item]

@app.get('/api/health')
def health(): return {'ok':True,'service':'Atoztoys Advanced V11'}
@app.get('/api/settings')
def settings():
    with db() as c: return {r['key']:r['value'] for r in c.execute('SELECT * FROM settings').fetchall()}
@app.put('/api/admin/settings')
def save_setting(x:SettingIn,u=Depends(admin)):
    if x.key not in DEFAULTS: raise HTTPException(400,'Setting not allowed')
    with db() as c: c.execute('INSERT INTO settings VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(x.key,x.value))
    return {'ok':True}

@app.get('/api/categories')
def categories():
    with db() as c: rows=c.execute('SELECT * FROM categories WHERE active=TRUE ORDER BY sort_order,id').fetchall()
    return rows
@app.post('/api/admin/categories')
def add_cat(x:CategoryIn,u=Depends(admin)):
    with db() as c: return c.execute('INSERT INTO categories(parent_id,name,description,image_url,sort_order) VALUES(%s,%s,%s,%s,%s) RETURNING *',(x.parent_id,x.name,x.description,x.image_url,x.sort_order)).fetchone()
@app.put('/api/admin/categories/{cid}')
def edit_cat(cid:int,x:CategoryIn,u=Depends(admin)):
    with db() as c: c.execute('UPDATE categories SET parent_id=%s,name=%s,description=%s,image_url=%s,sort_order=%s WHERE id=%s',(x.parent_id,x.name,x.description,x.image_url,x.sort_order,cid))
    return {'ok':True}
@app.delete('/api/admin/categories/{cid}')
def del_cat(cid:int,u=Depends(admin)):
    with db() as c: c.execute('UPDATE categories SET active=FALSE WHERE id=%s',(cid,))
    return {'ok':True}

@app.get('/api/products')
def products(q:Optional[str]=None,category_id:Optional[int]=None,limit:int=100,offset:int=0):
    limit=max(1,min(limit,200)); offset=max(0,offset)
    with db() as c:
        sql='''SELECT p.*, c.name AS category_name FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=TRUE'''; args=[]
        if q: sql+=' AND (p.name ILIKE %s OR p.description ILIKE %s OR c.name ILIKE %s)'; args += [f'%{q}%',f'%{q}%',f'%{q}%']
        if category_id: sql+=' AND p.category_id=%s'; args.append(category_id)
        rows=c.execute(sql+' ORDER BY p.id DESC LIMIT %s OFFSET %s',args+[limit,offset]).fetchall()
        for r in rows: r['images']=[f"/api/product-images/{x['id']}" for x in c.execute('SELECT id FROM product_images WHERE product_id=%s ORDER BY id',(r['id'],)).fetchall()]
        return rows
@app.get('/api/products/{pid}')
def product(pid:int):
    with db() as c:
        r=c.execute('SELECT p.*,c.name AS category_name FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.id=%s AND p.active=TRUE',(pid,)).fetchone()
        if not r: raise HTTPException(404,'Product not found')
        r['images']=[f"/api/product-images/{x['id']}" for x in c.execute('SELECT id FROM product_images WHERE product_id=%s ORDER BY id',(pid,)).fetchall()]
        return r
@app.post('/api/admin/products')
def add_product(x:ProductIn,u=Depends(admin)):
    with db() as c: return c.execute('INSERT INTO products(category_id,name,price,old_price,sku,emoji,description,stock,image_url) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',(x.category_id,x.name,x.price,x.old_price,x.sku,x.emoji,x.description,x.stock,x.image_url)).fetchone()
@app.put('/api/admin/products/{pid}')
def edit_product(pid:int,x:ProductIn,u=Depends(admin)):
    with db() as c: c.execute('UPDATE products SET category_id=%s,name=%s,price=%s,old_price=%s,sku=%s,emoji=%s,description=%s,stock=%s,image_url=%s,updated_at=now() WHERE id=%s',(x.category_id,x.name,x.price,x.old_price,x.sku,x.emoji,x.description,x.stock,x.image_url,pid))
    return {'ok':True}
@app.delete('/api/admin/products/{pid}')
def delete_product(pid:int,u=Depends(admin)):
    with db() as c: c.execute('UPDATE products SET active=FALSE,updated_at=now() WHERE id=%s',(pid,))
    return {'ok':True}
@app.post('/api/admin/products/{pid}/images')
async def upload_images(pid:int,files:list[UploadFile]=File(...),u=Depends(admin)):
    out=[]
    with db() as c:
        if not c.execute('SELECT id FROM products WHERE id=%s',(pid,)).fetchone(): raise HTTPException(404,'Product not found')
        for f in files:
            if f.content_type not in ('image/jpeg','image/png','image/webp'): continue
            data=await f.read()
            if len(data)>5*1024*1024: continue
            r=c.execute('INSERT INTO product_images(product_id,data,mime) VALUES(%s,%s,%s) RETURNING id',(pid,data,f.content_type)).fetchone(); out.append('/api/product-images/'+str(r['id']))
    return {'images':out}
@app.get('/api/product-images/{iid}')
def image(iid:int):
    with db() as c: r=c.execute('SELECT data,mime FROM product_images WHERE id=%s',(iid,)).fetchone()
    if not r: raise HTTPException(404,'Image not found')
    return Response(content=bytes(r['data']),media_type=r['mime'],headers={'Cache-Control':'public,max-age=86400'})

@app.post('/api/admin/media')
async def upload_media(kind:str='general',file:UploadFile=File(...),u=Depends(admin)):
    if file.content_type not in ('image/jpeg','image/png','image/webp','image/svg+xml'): raise HTTPException(400,'Unsupported image')
    data=await file.read()
    if len(data)>5*1024*1024: raise HTTPException(400,'Image too large')
    with db() as c:
        r=c.execute('INSERT INTO media(kind,data,mime) VALUES(%s,%s,%s) RETURNING id',(kind,data,file.content_type)).fetchone()
        return {'url':'/api/media/'+str(r['id'])}
@app.get('/api/media/{mid}')
def media(mid:int):
    with db() as c: r=c.execute('SELECT data,mime FROM media WHERE id=%s',(mid,)).fetchone()
    if not r: raise HTTPException(404,'Media not found')
    return Response(content=bytes(r['data']),media_type=r['mime'],headers={'Cache-Control':'public,max-age=86400'})

@app.get('/api/ads')
def ads():
    with db() as c: return c.execute('SELECT * FROM ads WHERE active=TRUE ORDER BY sort_order,id DESC').fetchall()
@app.post('/api/admin/ads')
def add_ad(x:AdIn,u=Depends(admin)):
    with db() as c: return c.execute('INSERT INTO ads(title,subtitle,image_url,link,position,active,sort_order) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *',(x.title,x.subtitle,x.image_url,x.link,x.position,x.active,x.sort_order)).fetchone()
@app.put('/api/admin/ads/{aid}')
def edit_ad(aid:int,x:AdIn,u=Depends(admin)):
    with db() as c: c.execute('UPDATE ads SET title=%s,subtitle=%s,image_url=%s,link=%s,position=%s,active=%s,sort_order=%s WHERE id=%s',(x.title,x.subtitle,x.image_url,x.link,x.position,x.active,x.sort_order,aid))
    return {'ok':True}
@app.delete('/api/admin/ads/{aid}')
def del_ad(aid:int,u=Depends(admin)):
    with db() as c: c.execute('DELETE FROM ads WHERE id=%s',(aid,))
    return {'ok':True}

@app.post('/api/auth/login')
def login(a:Auth):
    with db() as c:
        r=c.execute('SELECT * FROM users WHERE mobile=%s AND password_hash=%s',(a.mobile,ph(a.password))).fetchone()
        if not r: raise HTTPException(401,'Invalid mobile or password')
        t=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions(token,user_id) VALUES(%s,%s)',(t,r['id'])); return {'token':t,'user':r}
@app.post('/api/auth/register')
def register(a:Auth):
    with db() as c:
        try: r=c.execute('INSERT INTO users(name,mobile,password_hash) VALUES(%s,%s,%s) RETURNING *',(a.name,a.mobile,ph(a.password))).fetchone()
        except psycopg.errors.UniqueViolation: raise HTTPException(409,'Mobile already registered')
        t=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions(token,user_id) VALUES(%s,%s)',(t,r['id'])); return {'token':t,'user':r}

@app.post('/api/orders')
def order(o:OrderIn,u=Depends(current)):
    if not o.items: raise HTTPException(400,'Cart is empty')
    with db() as c:
        total=0; rows=[]
        for it in o.items:
            p=c.execute('SELECT id,name,price,stock FROM products WHERE id=%s AND active=TRUE FOR UPDATE',(it.product_id,)).fetchone()
            if not p or p['stock']<it.qty: raise HTTPException(400,'Product unavailable or insufficient stock')
            total += p['price']*it.qty; rows.append((p,it.qty))
        r=c.execute('INSERT INTO orders(user_id,customer_name,mobile,address,total,payment_method) VALUES(%s,%s,%s,%s,%s,%s) RETURNING id',(u['id'] if u else None,o.customer_name,o.mobile,o.address,total,o.payment_method)).fetchone(); oid=r['id']
        for p,q in rows:
            c.execute('INSERT INTO order_items(order_id,product_id,name,qty,price) VALUES(%s,%s,%s,%s,%s)',(oid,p['id'],p['name'],q,p['price'])); c.execute('UPDATE products SET stock=stock-%s WHERE id=%s',(q,p['id']))
        return {'ok':True,'order_id':oid,'total':total}

@app.get('/api/admin/stats')
def stats(u=Depends(admin)):
    with db() as c: return {'products':c.execute('SELECT count(*) AS n FROM products WHERE active=TRUE').fetchone()['n'],'categories':c.execute('SELECT count(*) AS n FROM categories WHERE active=TRUE').fetchone()['n'],'customers':c.execute("SELECT count(*) AS n FROM users WHERE role='customer'").fetchone()['n'],'orders':c.execute('SELECT count(*) AS n FROM orders').fetchone()['n'],'revenue':c.execute("SELECT coalesce(sum(total),0) AS n FROM orders WHERE payment_method='COD' OR payment_status='paid'").fetchone()['n']}
@app.get('/api/admin/orders')
def admin_orders(u=Depends(admin)):
    with db() as c: return c.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 300').fetchall()
@app.put('/api/admin/orders/{oid}')
def order_status(oid:int,status:str,u=Depends(admin)):
    allowed={'new','confirmed','packed','shipped','delivered','cancelled'}
    if status not in allowed: raise HTTPException(400,'Invalid status')
    with db() as c: c.execute('UPDATE orders SET order_status=%s WHERE id=%s',(status,oid))
    return {'ok':True}

@app.get('/',response_class=HTMLResponse)
def home(): return HTML

HTML='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Atoztoys • Next Generation Toy Store</title><meta name="description" content="Atoztoys colorful toy store"><style>
:root{--p:#6c2cff;--a:#ff3f9d;--y:#ffd83d;--c:#36d9ff;--ink:#22233b;--bg:#fff8fb}*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;color:var(--ink);background:radial-gradient(circle at 10% 10%,#e9faff 0 14%,transparent 30%),radial-gradient(circle at 90% 0,#ffe8f5 0 15%,transparent 30%),var(--bg)}button,input,textarea,select{font:inherit}.top{background:#17102d;color:#fff;text-align:center;padding:8px;font-size:13px}.nav{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:12px;padding:12px 4%;background:#ffffffed;backdrop-filter:blur(16px);box-shadow:0 8px 30px #28114b12}.brand{display:flex;align-items:center;gap:9px;font-weight:1000;font-size:23px;white-space:nowrap}.logo{width:43px;height:43px;border-radius:14px;background:linear-gradient(135deg,var(--p),var(--a));display:grid;place-items:center;color:white;font-size:24px;box-shadow:0 8px 18px #6c2cff55}.search{flex:1;max-width:650px;margin:auto;border:2px solid #ece8f4;border-radius:99px;padding:12px 18px;background:white;outline:none}.search:focus{border-color:var(--p)}.pill{border:0;border-radius:99px;padding:11px 15px;font-weight:900;cursor:pointer;background:#f3effb}.hero{margin:25px 4%;padding:45px 6%;border-radius:38px;overflow:hidden;color:white;position:relative;background:linear-gradient(120deg,#5b27e9,#9c3dff 48%,#ff3f9d);box-shadow:0 25px 60px #6c2cff33}.hero:before,.hero:after{content:'';position:absolute;border-radius:50%;background:#fff2;filter:blur(2px)}.hero:before{width:280px;height:280px;right:5%;top:-80px}.hero:after{width:160px;height:160px;right:28%;bottom:-80px}.heroContent{position:relative;z-index:2;max-width:680px}.badge{display:inline-block;padding:8px 13px;border-radius:99px;background:#fff2;font-weight:900}.hero h1{font-size:clamp(42px,7vw,78px);line-height:.95;margin:18px 0}.hero p{font-size:18px;line-height:1.6;max-width:620px}.heroArt{position:absolute;right:7%;bottom:10%;font-size:110px;transform:rotate(-5deg);filter:drop-shadow(0 15px 10px #0003)}.btn{border:0;border-radius:15px;padding:13px 18px;font-weight:950;cursor:pointer;transition:.2s}.btn:hover{transform:translateY(-2px)}.primary{background:var(--y);color:#332100}.pink{background:var(--a);color:#fff}.white{background:#fff;color:var(--p)}.wrap{padding:0 4% 60px}.sectionHead{display:flex;align-items:end;justify-content:space-between;gap:15px;margin:30px 0 14px}.sectionHead h2{margin:0;font-size:30px}.cats{display:flex;gap:12px;overflow:auto;padding:5px 0 15px}.cat{min-width:145px;border:0;border-radius:22px;padding:20px 15px;text-align:left;font-weight:950;cursor:pointer;background:#fff;box-shadow:0 12px 30px #28114b12}.cat span{font-size:38px;display:block;margin-bottom:8px}.cat:hover{outline:3px solid #e6ddff}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.card{background:#fff;border-radius:24px;padding:11px;box-shadow:0 15px 35px #28114b12;cursor:pointer;transition:.2s}.card:hover{transform:translateY(-5px);box-shadow:0 22px 45px #28114b1f}.photo{height:220px;border-radius:19px;background:linear-gradient(145deg,#effcff,#fff0f7);display:grid;place-items:center;font-size:90px;overflow:hidden}.photo img{width:100%;height:100%;object-fit:contain}.card h3{margin:11px 5px 5px}.muted{color:#7a7890}.price{font-size:22px;font-weight:1000;margin-left:5px}.old{text-decoration:line-through;color:#aaa;margin-left:7px}.sale{display:inline-block;background:#ffe5f0;color:#c50055;padding:5px 8px;border-radius:9px;font-size:12px;font-weight:900;margin:7px 5px}.modal{position:fixed;inset:0;background:#180c2dcc;z-index:50;display:none;align-items:center;justify-content:center;padding:16px}.modal.open{display:flex}.sheet{background:white;border-radius:28px;max-width:980px;width:100%;max-height:92vh;overflow:auto;padding:22px}.productDetail{display:grid;grid-template-columns:1fr 1fr;gap:25px}.gallery{min-height:420px;background:#f5f3ff;border-radius:24px;display:grid;place-items:center;font-size:140px;overflow:hidden}.gallery img{max-width:100%;max-height:520px;object-fit:contain}.thumbs{display:flex;gap:8px;margin-top:10px}.thumb{width:64px;height:64px;object-fit:cover;border-radius:12px;border:2px solid #eee}.admin{display:none}.adminNav{display:flex;gap:8px;flex-wrap:wrap}.panel{background:#fff;border-radius:24px;padding:20px;margin-top:15px;box-shadow:0 15px 35px #28114b12}.form{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.form input,.form textarea,.form select{width:100%;padding:12px;border:2px solid #eee;border-radius:12px}.form textarea{min-height:90px}.full{grid-column:1/-1}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.stat{padding:17px;border-radius:18px;background:linear-gradient(135deg,#f5f0ff,#fff0f7)}.stat b{display:block;font-size:30px}.table{overflow:auto}.row{display:grid;grid-template-columns:1.4fr .7fr .7fr .8fr;gap:8px;padding:11px;border-bottom:1px solid #eee;align-items:center}.ad{margin:20px 0;border-radius:25px;padding:22px;background:linear-gradient(120deg,#fff0a7,#d8f8ff);display:flex;justify-content:space-between;align-items:center}.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#19132b;color:white;padding:12px 18px;border-radius:99px;display:none;z-index:90}@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}.heroArt{font-size:70px}.productDetail{grid-template-columns:1fr}.form{grid-template-columns:1fr 1fr}.stats{grid-template-columns:1fr 1fr}}@media(max-width:600px){.brand{font-size:18px}.nav{padding:9px 3%}.search{order:5;flex-basis:100%}.hero{margin:14px 3%;padding:30px 7%}.heroArt{position:relative;right:auto;bottom:auto;text-align:right;font-size:60px}.grid{grid-template-columns:repeat(2,1fr);gap:9px}.photo{height:155px;font-size:60px}.form{grid-template-columns:1fr}.stats{grid-template-columns:1fr 1fr}.row{grid-template-columns:1fr 1fr}.sheet{padding:14px}}
</style></head><body><div class="top" id="ship">🎉 Free shipping above ₹499 • COD available • Colorful shopping for little smiles</div><nav class="nav"><div class="brand"><div class="logo" id="logo">🧸</div><span id="brand">Atoztoys</span></div><input class="search" id="search" placeholder="🔎 Search toys, keychains, piggy banks..."><button class="pill" onclick="openCart()">🛒 <span id="count">0</span></button><button class="pill" onclick="login()">👤</button></nav><section class="hero"><div class="heroContent"><span class="badge" id="badge">🌈 PLAY • GIFT • SMILE</span><h1 id="heroTitle">Little Toys.<br>Big Adventures.</h1><p id="heroText">Steel mini toys, piggy banks, mini almirahs, keychains and fun gifts for every little smile.</p><button class="btn primary" onclick="document.getElementById('shop').scrollIntoView({behavior:'smooth'})" id="heroBtn">Explore Toys ✨</button></div><div class="heroArt">🧸 🐷 🚗 🔑</div></section><main class="wrap"><div id="adArea"></div><div class="sectionHead"><h2>Explore Categories ✨</h2></div><div class="cats" id="cats"></div><section id="shop"><div class="sectionHead"><h2 id="shopTitle">Trending Toys ⭐</h2><button class="pill" onclick="loadProducts()">View all</button></div><div class="grid" id="products"></div></section><section class="admin wrap" id="admin"><div class="sectionHead"><h2>⚙️ Atoztoys Control Center</h2><button class="pill" onclick="closeAdmin()">Close</button></div><div class="stats" id="stats"></div><div class="panel"><h3>✏️ Website & Brand</h3><div class="form" id="settingsForm"></div><button class="btn pink" onclick="saveSettings()">Save Website Changes</button></div><div class="panel"><h3>📂 Unlimited Category Tree</h3><div class="form"><select id="catParent"><option value="">Main category</option></select><input id="catName" placeholder="Category / sub-category name"><input id="catDesc" placeholder="Description"><input id="catImg" placeholder="Image URL (optional)"><button class="btn pink" onclick="addCategory()">+ Add Category</button></div><div id="catAdmin"></div></div><div class="panel"><h3>🧸 Products — Add & Edit from here</h3><div class="form"><select id="pCat"></select><input id="pName" placeholder="Product name"><input id="pPrice" type="number" placeholder="Price"><input id="pOld" type="number" placeholder="Old price"><input id="pStock" type="number" placeholder="Stock"><input id="pEmoji" value="🧸" placeholder="Emoji"><textarea class="full" id="pDesc" placeholder="Description"></textarea><input id="pImageUrl" placeholder="Optional image URL"><button class="btn pink" onclick="addProduct()">+ Add Product</button></div><div id="productAdmin"></div></div><div class="panel"><h3>📸 Product Photos — phone se upload</h3><select id="photoProduct"></select><input type="file" id="photoFiles" accept="image/jpeg,image/png,image/webp" multiple><button class="btn pink" onclick="uploadPhotos()">Upload Photos</button></div><div class="panel"><h3>📢 Ads & Banners</h3><div class="form"><input id="adTitle" placeholder="Ad title"><input id="adSub" placeholder="Ad subtitle"><input id="adImg" placeholder="Image URL"><input id="adLink" placeholder="Click link / product URL"><select id="adPos"><option>hero</option><option>home</option><option>category</option></select><button class="btn pink" onclick="addAd()">+ Add Ad</button></div><div id="adAdmin"></div></div><div class="panel"><h3>📦 Orders</h3><div id="orders"></div></div></section></main><div class="modal" id="modal"><div class="sheet" id="sheet"></div></div><div class="toast" id="toast"></div><script>
let token=localStorage.getItem('atoz_token')||'',cart=JSON.parse(localStorage.getItem('atoz_cart')||'[]'),allProducts=[],cats=[];const $=id=>document.getElementById(id);function toast(t){$('toast').textContent=t;$('toast').style.display='block';setTimeout(()=>$('toast').style.display='none',2200)}async function api(u,o={}){o.headers={...(o.headers||{}),...(token?{Authorization:'Bearer '+token}:{})};if(o.body&&!(o.body instanceof FormData))o.headers['Content-Type']='application/json';let r=await fetch(u,o),d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.detail||'Something went wrong');return d}
function cartCount(){$('count').textContent=cart.reduce((a,x)=>a+x.qty,0);localStorage.setItem('atoz_cart',JSON.stringify(cart))}function add(id){let x=cart.find(x=>x.product_id==id);x?x.qty++:cart.push({product_id:id,qty:1});cartCount();toast('Added to cart 🛒')}function closeModal(){$('modal').classList.remove('open')}function openCart(){let items=cart.map(x=>{let p=allProducts.find(p=>p.id==x.product_id);return p?`<div class="row"><span>${p.emoji} ${p.name}</span><span>₹${p.price}</span><span>×${x.qty}</span><button class="pill" onclick="removeCart(${p.id})">Remove</button></div>`:''}).join('');let total=cart.reduce((s,x)=>{let p=allProducts.find(p=>p.id==x.product_id);return s+(p?p.price*x.qty:0)},0);$('sheet').innerHTML=`<h2>🛒 Your Cart</h2>${items||'<p>Your cart is empty.</p>'}<h3>Total: ₹${total}</h3><button class="btn pink" onclick="checkout()">Checkout</button> <button class="pill" onclick="closeModal()">Close</button>`;$('modal').classList.add('open')}function removeCart(id){cart=cart.filter(x=>x.product_id!=id);cartCount();openCart()}async function checkout(){if(!cart.length)return toast('Cart empty');let name=prompt('Customer name'),mobile=prompt('Mobile number'),address=prompt('Full delivery address');if(!name||!mobile||!address)return;try{let r=await api('/api/orders',{method:'POST',body:JSON.stringify({customer_name:name,mobile,address,payment_method:'COD',items:cart})});cart=[];cartCount();closeModal();toast('Order #'+r.order_id+' placed 🎉')}catch(e){toast(e.message)}}
async function loadSettings(){let s=await api('/api/settings');$('brand').textContent=s.brand_name;if(s.logo_url){$('logo').innerHTML='<img src=\"'+s.logo_url+'\" alt=\"Atoztoys logo\" style=\"width:100%;height:100%;object-fit:contain;border-radius:14px\">';}$('badge').textContent=s.tagline;$('heroTitle').innerHTML=s.hero_title.replace(/\\n/g,'<br>');$('heroText').textContent=s.hero_text;$('heroBtn').textContent=s.hero_button;$('ship').textContent='🎉 '+s.shipping_text+' • '+s.cod_text+' • '+s.support_text}
async function loadCats(){cats=await api('/api/categories');let roots=cats.filter(c=>!c.parent_id);$('cats').innerHTML=roots.map(c=>`<button class="cat" onclick="catClick(${c.id})"><span>${c.image_url||'🧸'}</span>${c.name}</button>`).join('');$('catParent').innerHTML='<option value="">Main category</option>'+cats.map(c=>`<option value="${c.id}">${'— '.repeat(depth(c))}${c.name}</option>`).join('');$('pCat').innerHTML=cats.map(c=>`<option value="${c.id}">${c.name}</option>`).join('');$('photoProduct').innerHTML=allProducts.map(p=>`<option value="${p.id}">${p.name}</option>`).join('')}function depth(c){let n=0,p=c.parent_id;while(p){let x=cats.find(z=>z.id==p);if(!x)break;n++;p=x.parent_id}return n}function descendants(id){return cats.filter(c=>c.parent_id==id)}async function catClick(id){let children=descendants(id);if(children.length){$('cats').innerHTML=children.map(c=>`<button class="cat" onclick="catClick(${c.id})"><span>${c.image_url||'🧸'}</span>${c.name}</button>`).join('');loadProducts(id)}else loadProducts(id)}
async function loadProducts(cid=null){let u='/api/products'+(cid?'?category_id='+cid:'');allProducts=await api(u);$('products').innerHTML=allProducts.map(p=>`<article class="card" onclick="openProduct(${p.id})"><div class="photo">${p.images?.[0]?`<img src="${p.images[0]}">`:p.image_url?`<img src="${p.image_url}">`:p.emoji}</div><span class="sale">${p.stock>0?'IN STOCK':'SOLD OUT'}</span><h3>${p.name}</h3><span class="price">₹${p.price}</span>${p.old_price?`<span class="old">₹${p.old_price}</span>`:''}<p class="muted">${p.description||''}</p></article>`).join('')||'<p>No products found.</p>';cartCount()}
async function openProduct(id){let p=await api('/api/products/'+id);$('sheet').innerHTML=`<div class="productDetail"><div><div class="gallery">${p.images?.[0]?`<img id="mainImg" src="${p.images[0]}">`:p.emoji}</div><div class="thumbs">${(p.images||[]).map(i=>`<img class="thumb" src="${i}" onclick="$('mainImg').src='${i}'">`).join('')}</div></div><div><span class="sale">${p.category_name||'Toy'}</span><h1>${p.name}</h1><h2>₹${p.price} ${p.old_price?`<del class="muted">₹${p.old_price}</del>`:''}</h2><p>${p.description||'Lovely Atoztoys product.'}</p><p>📦 Stock: ${p.stock}</p><button class="btn pink" onclick="add(${p.id});closeModal()">Add to Cart 🛒</button> <button class="btn primary" onclick="add(${p.id});openCart()">Buy Now</button></div></div><br><button class="pill" onclick="closeModal()">Close</button>`;$('modal').classList.add('open')}
async function login(){let mobile=prompt('Admin/customer mobile'),password=prompt('Password');if(!mobile||!password)return;try{let d=await api('/api/auth/login',{method:'POST',body:JSON.stringify({mobile,password,name:'x'})});token=d.token;localStorage.setItem('atoz_token',token);toast('Login successful');if(d.user.role==='admin')openAdmin()}catch(e){toast(e.message)}}
async function openAdmin(){$('admin').style.display='block';$('admin').scrollIntoView({behavior:'smooth'});try{let s=await api('/api/admin/stats');$('stats').innerHTML=Object.entries(s).map(([k,v])=>`<div class="stat">${k}<b>${v}</b></div>`).join('');let st=await api('/api/settings');$('settingsForm').innerHTML=Object.entries(st).map(([k,v])=>`<input id="s_${k}" value="${String(v).replaceAll('"','&quot;')}" placeholder="${k}">`).join('');await renderAdminCats();await renderAdminProducts();await renderAdminAds();let os=await api('/api/admin/orders');$('orders').innerHTML=os.map(o=>`<div class="row"><span><b>#${o.id}</b> ${o.customer_name}</span><span>₹${o.total}</span><span>${o.order_status}</span><button class="pill" onclick="setOrder(${o.id})">Status</button></div>`).join('')||'No orders';}catch(e){toast(e.message)}}function closeAdmin(){$('admin').style.display='none'}
async function saveSettings(){let st=await api('/api/settings');try{for(let k of Object.keys(st)){let e=$('s_'+k);if(e)await api('/api/admin/settings',{method:'PUT',body:JSON.stringify({key:k,value:e.value})})}await loadSettings();toast('Website updated ✨')}catch(e){toast(e.message)}}
async function addCategory(){try{await api('/api/admin/categories',{method:'POST',body:JSON.stringify({parent_id:$('catParent').value?+$('catParent').value:null,name:$('catName').value,description:$('catDesc').value,image_url:$('catImg').value})});$('catName').value='';$('catDesc').value='';$('catImg').value='';await loadCats();await renderAdminCats();toast('Category added')}catch(e){toast(e.message)}}async function renderAdminCats(){let tree=cats.map(c=>`<div class="row"><span>${'— '.repeat(depth(c))}${c.image_url||'🧸'} ${c.name}</span><span>${c.id}</span><span>${c.parent_id||'Main'}</span><button class="pill" onclick="delCat(${c.id})">Delete</button></div>`).join('');$('catAdmin').innerHTML=tree}async function delCat(id){if(confirm('Delete category?')){await api('/api/admin/categories/'+id,{method:'DELETE'});await loadCats();await renderAdminCats()}}
async function addProduct(){try{let p=await api('/api/admin/products',{method:'POST',body:JSON.stringify({category_id:+$('pCat').value,name:$('pName').value,price:+$('pPrice').value,old_price:$('pOld').value?+$('pOld').value:null,stock:+$('pStock').value,emoji:$('pEmoji').value,description:$('pDesc').value,image_url:$('pImageUrl').value})});$('pName').value='';toast('Product added #'+p.id);await loadProducts();await loadCats();await renderAdminProducts()}catch(e){toast(e.message)}}async function renderAdminProducts(){$('productAdmin').innerHTML=allProducts.map(p=>`<div class="row"><span>${p.emoji} <b>${p.name}</b></span><span>₹${p.price}</span><span>${p.stock} stock</span><button class="pill" onclick="editProduct(${p.id})">✏️ Edit</button><button class="pill" onclick="delProduct(${p.id})">🗑️ Delete</button></div>`).join('')||'No products yet.'}async function editProduct(id){let p=allProducts.find(x=>x.id==id);if(!p)return;let name=prompt('Product name',p.name);if(name===null)return;let price=prompt('Price',p.price);if(price===null)return;let old=prompt('Old price (optional)',p.old_price||'');let stock=prompt('Stock',p.stock);if(stock===null)return;let desc=prompt('Description',p.description||'');try{await api('/api/admin/products/'+id,{method:'PUT',body:JSON.stringify({category_id:p.category_id,name,price:+price,old_price:old?+old:null,sku:p.sku||'',emoji:p.emoji||'🧸',description:desc||'',stock:+stock,image_url:p.image_url||''})});await loadProducts();await renderAdminProducts();toast('Product updated ✨')}catch(e){toast(e.message)}}async function delProduct(id){if(confirm('Delete product?')){await api('/api/admin/products/'+id,{method:'DELETE'});await loadProducts();await renderAdminProducts();toast('Deleted')}}async function uploadPhotos(){let fs=$('photoFiles').files;if(!fs.length)return toast('Select photo first');let f=new FormData();for(let x of fs)f.append('files',x);try{await api('/api/admin/products/'+$('photoProduct').value+'/images',{method:'POST',body:f});await loadProducts();await renderAdminProducts();toast('Photos uploaded 📸')}catch(e){toast(e.message)}}
async function addAd(){try{await api('/api/admin/ads',{method:'POST',body:JSON.stringify({title:$('adTitle').value,subtitle:$('adSub').value,image_url:$('adImg').value,link:$('adLink').value,position:$('adPos').value,active:true})});await renderAdminAds();toast('Ad added 📢')}catch(e){toast(e.message)}}async function renderAdminAds(){let a=await api('/api/ads');$('adAdmin').innerHTML=a.map(x=>`<div class="ad"><div><b>${x.title}</b><br>${x.subtitle}<br><small>${x.position} • ${x.active?'Active':'Hidden'}</small></div><button class="pill" onclick="editAd(${x.id})">✏️ Edit</button><button class="pill" onclick="delAd(${x.id})">🗑️ Delete</button></div>`).join('')||'No ads yet.'}async function editAd(id){let a=await api('/api/ads');let x=a.find(z=>z.id==id);if(!x)return;let title=prompt('Ad title',x.title);if(title===null)return;let sub=prompt('Ad subtitle',x.subtitle||'');let img=prompt('Image URL',x.image_url||'');let link=prompt('Click link',x.link||'');try{await api('/api/admin/ads/'+id,{method:'PUT',body:JSON.stringify({title,subtitle:sub||'',image_url:img||'',link:link||'',position:x.position,active:x.active,sort_order:x.sort_order||0})});await renderAdminAds();await loadAds();toast('Ad updated ✨')}catch(e){toast(e.message)}}async function delAd(id){await api('/api/admin/ads/'+id,{method:'DELETE'});renderAdminAds()}async function setOrder(id){let s=prompt('Status: new / confirmed / packed / shipped / delivered / cancelled','confirmed');if(s){await api('/api/admin/orders/'+id+'?status='+encodeURIComponent(s),{method:'PUT'});openAdmin()}}
async function loadAds(){let a=await api('/api/ads');$('adArea').innerHTML=a.filter(x=>x.position==='home').map(x=>`<div class="ad" onclick="location.href='${x.link||'#'}'"><div><h2>${x.title}</h2><p>${x.subtitle}</p></div>${x.image_url?`<img src="${x.image_url}" style="max-height:110px;max-width:45%;object-fit:contain">`:''}</div>`).join('')}
$('search').oninput=async e=>{allProducts=await api('/api/products?q='+encodeURIComponent(e.target.value));$('products').innerHTML=allProducts.map(p=>`<article class="card" onclick="openProduct(${p.id})"><div class="photo">${p.images?.[0]?`<img src="${p.images[0]}">`:p.emoji}</div><h3>${p.name}</h3><span class="price">₹${p.price}</span></article>`).join('')};$('modal').onclick=e=>{if(e.target.id==='modal')closeModal()};(async()=>{try{await loadSettings();await loadProducts();await loadCats();await loadAds()}catch(e){toast(e.message)}})();
</script></body></html>'''
