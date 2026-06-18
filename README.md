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
- Recipient-key encrypted storage for new messages
- Encryption key rotation with legacy-message readability
- Unread message badges
- Online, offline, and last-seen status
- Typing indicator
- Sent, delivered, and read receipts
- Edit and delete sent messages
- Reply, forward, react to, and star messages
- Disappearing and scheduled messages
- Group polls, invite codes, and admin approval for joins
- Voice/video call UI with call history
- Image, audio, video, PDF, and document sharing
- Media scan, attachment thumbnails, and optional S3/MinIO object storage hooks
- Attachment deduplication and compressed media storage
- Search chats and search inside the selected chat
- Fuzzy typo-tolerant search
- Light/dark theme and accent color preference
- Pin and archive chats
- Block and report users
- In-app unread notifications
- Smart notifications for important unread chats
- Optional Firebase/OneSignal push notification hooks
- Versioned backup and restore
- Backup checksum verification
- Device/session management and logout from all devices
- User activity dashboard and admin moderation dashboard
- Profile photo upload
- Mail ID and contact number
- Country-code dropdown for supported regions
- SQLite storage by default, JSON import fallback, and PostgreSQL support
- Normalized PostgreSQL schema in `infra/database/schema.sql`
- Optional FastAPI WebSocket backend in `backend/main.py`
- Local PC, cloud VM, PaaS, and Docker deployment support

## Algorithms Added

- Message search ranking by exact match, sender match, frequency, and latest activity
- Unread priority sorting by pinned status, unread count, latest activity, and online status
- Spam detection and content moderation for repeated text, link floods, suspicious URLs, and blocked words
- Rate limiting for messages, login attempts, password resets, and friend requests
- Friend and group recommendations using mutual friends, shared groups, and recent activity
- Typing debounce to reduce storage writes while users type
- Read receipt state machine: sent, delivered, read, edited, and deleted
- Role-based group permissions: owner, admin, member, and muted member
- Message/media compression, attachment hashing, and duplicate payload reuse
- Smart notifications using unread count, pinned chats, mentions, and priority keywords
- Versioned backups with retention and timestamp restore
- Local chat summarization for long or unread conversations
- Toxicity scoring, abuse reputation, duplicate-message clustering, and adaptive rate limits
- Conversation topic labels and smart reply suggestions
- Offline message queue and retry flush on login
- Login anomaly flags for changed client IPs when provided by the platform

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

## Optional Realtime Backend

Run the FastAPI WebSocket backend:

```bash
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Connect the Streamlit UI to the realtime backend:

```bash
export CHATLITE_REALTIME_WS_URL="ws://localhost:8000/ws"
python3 -m streamlit run app.py
```

With Redis pub/sub for multiple backend instances:

```bash
export REDIS_URL="redis://localhost:6379/0"
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Health check:

```text
http://localhost:8000/health
```

Normalized PostgreSQL schema:

```bash
psql "$CHATLITE_DATABASE_URL" -f infra/database/schema.sql
```

## Kubernetes And Terraform

Structured deployment files are in:

```text
infra/
  README.md
  k8s/                  Kubernetes manifests for ChatLite
  terraform/            AWS EKS Terraform foundation
    k8s-app/            Optional Terraform app deployment
```

Terraform-first AWS EKS quick start:

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform validate
terraform plan
terraform apply

aws eks update-kubeconfig --region us-east-1 --name kscluster
```

Build and push the image to Docker Hub:

```bash
cd "/Users/anirudhtalluri/Documents/tab chating"
docker login -u anitalluri00
export IMAGE_URL="anitalluri00/chatlite:latest"
docker build -t "$IMAGE_URL" .
docker push "$IMAGE_URL"
```

Deploy the app:

If the Docker Hub repository is private, create the pull secret first:

```bash
kubectl apply -f infra/k8s/namespace.yaml
read -s DOCKERHUB_PASSWORD
kubectl -n chatlite create secret docker-registry dockerhub-credentials \
  --docker-server=https://index.docker.io/v1/ \
  --docker-username=anitalluri00 \
  --docker-password="$DOCKERHUB_PASSWORD"
kubectl -n chatlite patch serviceaccount default \
  -p '{"imagePullSecrets":[{"name":"dockerhub-credentials"}]}'
```

```bash
# Edit infra/k8s/secret.yaml first.
kubectl apply -k infra/k8s
kubectl -n chatlite port-forward svc/chatlite 8501:80
```

See `infra/README.md` for the full deployment notes.

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
- `infra/k8s` contains Kubernetes manifests.
- `infra/terraform` contains AWS EKS Terraform.
- `infra/terraform/k8s-app` contains optional app Terraform for existing clusters.
