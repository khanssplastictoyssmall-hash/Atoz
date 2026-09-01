ATOZ TOYS - FINAL ROOT DEPLOYMENT

FILES
- app.py
- index.html
- admin.html
- app.js
- admin.js
- styles.css
- requirements.txt
- render.yaml

RENDER START COMMAND
gunicorn app:app

BUILD COMMAND
pip install -r requirements.txt

RENDER ENVIRONMENT VARIABLES (4 TOTAL)
1. DATABASE_URL = Render Postgres INTERNAL Database URL
2. SECRET_KEY = Generate a long random secret in Render
3. ADMIN_USER = your admin username
4. ADMIN_PASSWORD = your admin password

DATABASE
This app creates these PostgreSQL tables automatically on first request:
settings, categories, products, ads

Use a separate logical database for this store if the same Postgres instance is shared with another website and that website may use the same table names.

IMPORTANT
- Do NOT create main.py.
- Do NOT use uvicorn.
- Do NOT add python-multipart.
- The checkout button is still a frontend placeholder until a payment/order provider is connected.
