# AtoZ Toys & Keychain V9 — Production-Ready Foundation

## Included
- Responsive colorful kids-toy storefront
- PostgreSQL database schema (users, products, images, orders, order items, settings)
- Admin authentication via environment-configured admin account
- Admin dashboard: products, stock, orders, editable website text
- Multi-image product uploads with basic type/size validation
- Customer registration/login
- COD order creation with stock locking/decrementing
- Health endpoint
- Render/host start command

## Deploy
Set these environment variables on your host:
- DATABASE_URL = your managed PostgreSQL connection string
- ADMIN_MOBILE = your admin mobile/login
- ADMIN_PASSWORD = a strong unique admin password

Build:
pip install -r requirements.txt

Start:
uvicorn app.main:app --host 0.0.0.0 --port $PORT

## Important production integrations
This foundation does NOT pretend that payment/courier accounts are already connected.
For real online payments, add a merchant payment gateway and webhook verification.
For shipping, add a courier/shipping API and shipment tracking webhooks.
For images at scale, use S3-compatible/object storage rather than local disk.
Use HTTPS, secure cookies/session rotation, CSRF protections where applicable,
rate limiting, image scanning, backups, monitoring and secrets management before
taking substantial customer traffic.
