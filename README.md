# Atoztoys Advanced V10

Folder-free Render/GitHub root. All deploy files are at repository root.

Build: `pip install -r requirements.txt`
Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

Required Render environment variables: DATABASE_URL, ADMIN_MOBILE, ADMIN_PASSWORD.

Admin is accessed from the live site by tapping the user/login button and signing in with ADMIN_MOBILE + ADMIN_PASSWORD.
