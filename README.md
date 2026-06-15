# ChatLite

A WhatsApp-style chat demo built with Python and Streamlit. It includes local
account creation, mail-ID login, friend requests, private chats, group chats,
profile editing, media sharing, unread counts, presence, message tools, and
SQLite/PostgreSQL-ready storage.

## Features

- Login, account creation, and demo password reset
- Friend requests
- Private chats between accepted friends
- Group chats with admin member management
- Encrypted message storage for chats
- Unread message badges
- Online, offline, and last-seen status
- Typing indicator
- Sent, delivered, and read receipts
- Edit and delete sent messages
- Image, audio, video, PDF, and document sharing
- Search chats and search inside the selected chat
- Light/dark theme and accent color preference
- Pin and archive chats
- Block and report users
- In-app unread notifications
- Profile photo upload
- Mail ID and contact number
- Country-code dropdown for supported regions
- SQLite storage by default, JSON import fallback, and PostgreSQL support
- Local PC, cloud VM, PaaS, and Docker deployment support

## Local Run

```bash
cd "/Users/anirudhtalluri/Documents/tab chating"
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

On this machine, Python 3.11.9 works cleanly:

```bash
PYENV_VERSION=3.11.9 python3 -m pip install -r requirements.txt
PYENV_VERSION=3.11.9 python3 -m streamlit run app.py
```

Open:

```text
http://localhost:8501
```

## Demo Login

Demo accounts log in with mail ID and use the password `demo123`:

- `demo@chatlite.local`
- `aisha@chatlite.local`
- `michael@chatlite.local`
- `nina@chatlite.local`

## Data Storage

By default the app stores users, friends, groups, profile data, messages, media,
and settings in SQLite:

```text
chatlite_data.sqlite3
```

For servers or Docker, set `CHATLITE_SQLITE_FILE` to a persistent path. Also set
`CHATLITE_APP_SECRET` and keep it stable; changing it later prevents old encrypted
messages from being decrypted.

```bash
export CHATLITE_SQLITE_FILE=/app/data/chatlite_data.sqlite3
export CHATLITE_APP_SECRET="replace-with-a-long-random-secret"
python3 -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

To use PostgreSQL, set `CHATLITE_DATABASE_URL`:

```bash
export CHATLITE_DATABASE_URL="postgresql://user:password@host:5432/chatlite"
export CHATLITE_APP_SECRET="replace-with-a-long-random-secret"
python3 -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

To keep the older JSON file mode, set:

```bash
export CHATLITE_STORAGE_BACKEND=json
export CHATLITE_DATA_FILE=/path/to/chatlite_data.json
```

## Docker Run

Build the image:

```bash
docker build -t chatlite .
```

Run it with persistent data:

```bash
docker run --rm -p 8501:8501 -v chatlite-data:/app/data chatlite
```

Open:

```text
http://localhost:8501
```

## Cloud Or Server Run

Most cloud platforms provide a `PORT` environment variable. This project includes
a `Procfile` and Dockerfile that use that value automatically.

Generic server command:

```bash
python3 -m pip install -r requirements.txt
export PORT=8501
export CHATLITE_SQLITE_FILE=/path/to/persistent/chatlite_data.sqlite3
export CHATLITE_APP_SECRET="replace-with-a-long-random-secret"
python3 -m streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT
```

For public servers, allow inbound traffic to the selected port in your firewall
or cloud security group.

## Included Deployment Files

- `.streamlit/config.toml` configures Streamlit for server-friendly headless mode.
- `Dockerfile` builds a portable container image.
- `.dockerignore` keeps local data and cache files out of Docker builds.
- `Procfile` works with PaaS providers that use web process commands.
- `runtime.txt` pins Python 3.11.9 for platforms that support it.
- `.gitignore` ignores generated local data and Python cache files.
