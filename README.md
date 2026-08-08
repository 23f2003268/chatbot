# Private 1-to-1 Chat Application

A secure, minimal, deployable private chat application intended strictly for personal 1-to-1 communication between **exactly one USER and one ADMIN**.

---

## Technical Stack

* **Language**: Python 3.10+
* **Backend Framework**: Flask
* **Database & ORM**: SQLite + SQLAlchemy
* **Authentication**: Password Hashing via Werkzeug (`generate_password_hash` / `check_password_hash`)
* **Session Security**: Server-managed session store with 15-second inactivity timeout & HTTP-only cookies
* **Real-time Engine**: HTTP Polling (Vanilla JS `fetch` every 1.5 seconds)
* **Frontend**: HTML5, Vanilla CSS, Vanilla JavaScript (No heavy frameworks or build steps)
* **Production Web Server**: Gunicorn

---

## Core Security & Architectural Features

1. **No Public Registration**: Account creation, registration, forgot-password, and public user listing interfaces do not exist. Only two pre-configured accounts (`ADMIN` and `USER`) exist.
2. **Server-Side Authorization**: Every API request is verified on the server. Role headers, URL parameters, or client-provided parameters are never trusted.
3. **15-Second Inactivity Timeout**: Authentication sessions expire automatically after 15 seconds of inactivity. Active API calls immediately renew the session timer.
4. **User Rolling Visibility Window**:
   - `USER` only receives messages from the **latest 3 minutes**.
   - `USER` only receives a **maximum of 10 cumulative messages** (from both USER + ADMIN).
   - `USER` cannot access messages sent prior to an admin "Clear Screen" boundary.
   - Older messages remain permanently stored for `ADMIN` until deleted.
5. **Private Image Storage**: Images uploaded by either account are stored outside static HTTP directories (`private_uploads/images/`) and served strictly through authenticated API routes (`GET /api/image/<id>`).
6. **Admin Management**:
   - **Clear User Screen**: Sets a server-side boundary timestamp (`user_visible_from`). Messages prior to this timestamp become inaccessible to `USER`, while remaining fully intact for `ADMIN`.
   - **Delete All Messages**: Permanently deletes all message records and image files from the server.

---

## Project Structure

```text
private-chat/
├── app.py                   # Main Flask app factory, page routes, static headers
├── config.py                # App configuration, environment variables loader
├── models.py                # SQLAlchemy DB models (User, Session, Message, SystemState)
├── auth.py                  # Server-side session verification, 15s inactivity check, decorators
├── chat.py                  # Chat API routes (/api/messages, /api/upload-image, admin routes)
├── requirements.txt         # Production dependencies
├── Procfile                 # Deployment process file (Gunicorn)
├── .env.example             # Template for environment configuration
├── .gitignore               # Excludes secrets, databases, uploads, caches
├── README.md                # Documentation & deployment guide
├── instance/
│   ├── .gitkeep
│   └── chat.db             # Private SQLite database (auto-created on startup)
├── private_uploads/
│   └── images/              # Private uploaded images storage (auto-created)
├── templates/
│   ├── login.html           # Minimal login page
│   ├── user.html            # User chat interface
│   └── admin.html           # Admin chat interface & management controls
├── static/
│   ├── style.css            # Vanilla CSS styling
│   └── chat.js              # Vanilla JS polling & API integration
└── tests/
    └── test_chat.py         # Pytest automated test suite
```

---

## Setup & Local Installation

### 1. Prerequisites
Ensure Python 3.10+ and `pip` are installed on your machine.

### 2. Clone Repository & Install Dependencies
```bash
git clone <your-repo-url>
cd private-chat

# Create virtual environment (optional but recommended)
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Credentials & Secrets
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` and set your desired production secrets and credentials:
```ini
SECRET_KEY=a-very-secret-and-unpredictable-string-here
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-admin-password
USER_USERNAME=user
USER_PASSWORD=your-secure-user-password
SESSION_INACTIVITY_TIMEOUT=15
```

> [!IMPORTANT]
> - Put your exact custom admin and user credentials into `.env`.
> - Never commit `.env` to Git repository. `.gitignore` is pre-configured to ignore `.env`.

### 4. Run Locally
```bash
python app.py
```
The application will automatically initialize the database at `instance/chat.db`, hash the configured passwords, seed the initial accounts, and start serving on `http://127.0.0.1:5000`.

---

## Running Tests

Run the comprehensive pytest test suite to verify security rules, visibility limits, inactivity timeouts, and upload checks:

```bash
pytest -v
```

---

## Production Deployment Guide (Render.com)

Here is the exact step-by-step guide to deploy your app on **Render**:

### Step 1: Push Code to GitHub
1. Create a new private repository on [GitHub](https://github.com).
2. Push your project code to GitHub:
   ```bash
   git init
   git add .
   git commit -m "Initial commit of private chat application"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git push -u origin main
   ```

### Step 2: Create a Web Service on Render
1. Log in to [Render](https://render.com).
2. Click **New +** and select **Web Service**.
3. Connect your GitHub repository.
4. Fill in the service configuration:
   - **Name**: `my-private-chat` (or any name you like)
   - **Region**: Choose the region closest to you
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

### Step 3: Add Environment Variables on Render
Under the **Environment Variables** section in Render, add the following keys and your secret values:

| Key | Value Example | Notes |
| :--- | :--- | :--- |
| `SECRET_KEY` | `super-secret-random-key-xyz987` | Cryptographic secret |
| `ADMIN_USERNAME` | `admin` | Username for ADMIN |
| `ADMIN_PASSWORD` | `YourAdminPass123!` | Password for ADMIN |
| `USER_USERNAME` | `user` | Username for USER |
| `USER_PASSWORD` | `YourUserPass123!` | Password for USER |
| `SESSION_INACTIVITY_TIMEOUT` | `15` | Session timeout in seconds |

### Step 4: Add Permanent Storage Disk (Recommended for Render)
To ensure chat history and uploaded images are never deleted when Render restarts or updates:
1. In your Render Web Service dashboard, go to **Disks** (or **Volumes**).
2. Click **Add Disk**:
   - **Name**: `chat-data`
   - **Mount Path**: `/var/data`
   - **Size**: 1 GB (or free tier default)
3. Add two more Environment Variables:
   - `DATABASE_URL`: `sqlite:////var/data/chat.db`
   - `UPLOAD_FOLDER`: `/var/data/images`

### Step 5: Deploy!
Click **Deploy Web Service**. Render will build the app, install dependencies, run Gunicorn, and give you a live HTTPS link (e.g. `https://my-private-chat.onrender.com`).


---

## Technical Details of Core Mechanics

### 15-Second Inactivity Session Expiration
- When a user logs in, a 64-character random token is generated and stored in SQLite `sessions` along with a `last_activity` timestamp.
- The session token is returned to the browser in an `HttpOnly`, `SameSite=Strict` cookie (`chat_session_id`).
- On **every** incoming request, `auth.py` checks `(datetime.utcnow() - session.last_activity)`.
- If the gap exceeds 15 seconds, the session is deleted from SQLite and HTTP 401 Unauthorized is returned, causing JavaScript to redirect to `/login`.
- If the request is active within 15 seconds, `last_activity` is renewed to `datetime.utcnow()`.

### User 3-Minute / 10-Message Visibility Rule
- When `USER` calls `GET /api/messages`:
  1. The server checks `three_minutes_ago = datetime.utcnow() - timedelta(minutes=3)`.
  2. The server checks the `SystemState.user_visible_from` timestamp (set when ADMIN clicks "Clear User Screen").
  3. The server takes the latest cutoff timestamp.
  4. The server queries messages matching `created_at >= cutoff`, orders by `created_at DESC`, and limits results to **10**.
  5. The server reverses the list and returns it to `USER`.
- Old or extra messages are **never sent over the network** to `USER`.

### ADMIN Clear User Screen
- When `ADMIN` clicks "Clear User Screen", `POST /api/admin/clear-user-screen` updates `SystemState.user_visible_from = datetime.utcnow()`.
- Future calls to `GET /api/messages` from `USER` will ignore messages prior to this boundary.
- `ADMIN` continues to see all historical messages as `ADMIN` bypasses the visibility boundary.

### Permanent Deletion
- When `ADMIN` clicks "Delete All Messages", `POST /api/admin/delete-all` deletes all records in the `messages` table and deletes all files in `private_uploads/images/`.
