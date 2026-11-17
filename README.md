# SmartTransit

SmartTransit is a React website with a Python/FastAPI backend and MySQL database.
It provides separate Citizen, Traffic Police, and Driver portals.

## Local setup: Windows + XAMPP

1. In XAMPP Control Panel, start **MySQL**. In phpMyAdmin, create an empty
   database named `smarttransit_db` using the `utf8mb4` character set.
2. Install the Python and frontend dependencies:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   Set-Location frontend
   npm.cmd install
   npm.cmd run build
   Set-Location ..
   ```

3. Copy `.env.example` to `.env`. The default URL is for a local XAMPP MySQL
   instance with its default `root` account and no password. If MySQL has a
   password, URL-encode it in `DATABASE_URL`. Generate the two secrets once,
   replace the placeholders in `.env`, and keep the same values for later
   restarts. Do not commit or share `.env`.

   ```powershell
   Copy-Item .env.example .env
   .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
   .\.venv\Scripts\python.exe -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
   ```

   Store both generated values privately. Back up the encryption key securely;
   it must remain unchanged to decrypt existing chat messages.
4. Create the tables:

   ```powershell
   .\.venv\Scripts\python.exe apply_migrations.py
   ```

5. Start the website:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn main:app --reload --env-file .env
   ```

   Open <http://127.0.0.1:8000>. API documentation is at
   <http://127.0.0.1:8000/docs>.

For frontend development, run `npm.cmd run dev` from `frontend/` in a second
terminal and open the Vite URL it prints. API requests are proxied to FastAPI.
Run `npm.cmd run build` again after frontend changes before serving the built
site from FastAPI.

Run the backend privacy and portal tests with:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Portals and account access

- Anyone can register as a Citizen. Registration does not ask for a NID or
  passport number.
- Police and Driver accounts cannot be self-created or unlocked by points.
  Configure an administrator locally, then use the Admin portal at
  <http://127.0.0.1:8000/admin> to create staff accounts after independently
  verifying each staff member's identity:

  ```powershell
  .\.venv\Scripts\python.exe configure_admin.py
  ```

  The admin email defaults to `admin@example.com`; the command prompts for a
  private password of at least 14 characters and stores only its PBKDF2 hash in
  `.env`. Restart the server after setup. Never use `admin1234` or another
  shared/default password. In the Admin portal, choose Police or Driver and
  enter that person's details and a unique initial password. Share the
  password privately; it is not shown again or stored in the staff roster.
- Demo seeding is disabled unless explicitly enabled for local testing. Set
  `SMARTTRANSIT_DEMO_CITIZEN_PASSWORD`, `SMARTTRANSIT_DEMO_POLICE_PASSWORD`, and
  `SMARTTRANSIT_DEMO_DRIVER_PASSWORD` to private local values before seeding.
  Never use demo accounts in production.

## Privacy and emergency assistance

- Passwords are stored as PBKDF2 hashes. Login sessions use an HttpOnly,
  SameSite cookie; the browser application does not put the session token in
  local storage.
- Chat messages are encrypted in MySQL with AES-256-GCM. Chat history is
  restricted to the signed-in user and portal. This is encryption at rest,
  **not** end-to-end encryption: the backend decrypts a message to display its
  own response.
- The help assistant uses a small local safety-information guide and does not
  send questions to an external AI service. It is not a substitute for police,
  emergency response, or legal advice.
- Migration `002_emergency_assistance.sql` adds the local emergency FAQ,
  hotline directory, source metadata, and police contact directory. Only 999
  is currently marked verified in the supplied hotline list; other supplied
  numbers are visibly marked as needing verification. Do not rely on a number
  marked "যাচাই বাকি" until it has been confirmed through a current official
  source.
- The attached Bangladesh Police contacts workbook is dated 2020-10-03. To
  load its Officer-in-Charge contact rows into `police_contacts` as
  **unverified historical records**, run:

  ```powershell
  .\.venv\Scripts\python.exe import_police_directory.py "C:\path\to\police-contacts.xlsx"
  ```

  These records are not used for nearby-station results. They must be checked
  against a current official source before anyone relies on their numbers.
- Nearby-station lookup uses a location only after the user explicitly shares
  it. Coordinates are used for that lookup and are not saved to chat history.
  The station directory contains only administrator-verified records and is
  empty after a fresh migration; add verified station details to
  `police_stations` before relying on nearby results.
- For immediate danger, call Bangladesh national emergency service **999**;
  do not wait for a chatbot reply.

For a public deployment, use HTTPS, set `APP_ENV=production`, provide strong
secret values and a restricted MySQL account, and secure backups. The current
fresh MySQL setup does not migrate existing PostgreSQL records.
