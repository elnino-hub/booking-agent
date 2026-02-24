# Booking Agent

An AI chatbot that manages your Google Calendar through natural conversation. Tell it to book, reschedule, or cancel meetings — it handles the rest.

Built with [n8n](https://n8n.io/) (workflow automation) + [FastAPI](https://fastapi.tiangolo.com/) (Python server) + GPT-4.1 (AI brain).

## What It Does

You chat with the bot, and it:
- Checks your calendar for upcoming events and free slots
- Books new meetings (with Google Meet links)
- Detects scheduling conflicts and warns you before booking
- Reschedules existing meetings to a new time
- Cancels meetings
- Remembers context across messages (multi-turn conversation)

## How It Works

There are two pieces that work together:

| Piece | What it does | Where it runs |
|-------|-------------|---------------|
| **Python API server** | Talks to Google Calendar on your behalf (reads events, books, cancels, etc.) | Your computer or a cloud host like Railway |
| **n8n workflow** | The AI brain — receives your chat messages, decides what to do, calls the Python server | n8n (cloud or self-hosted) |

```
You type a message
       ↓
n8n receives it → AI decides what to do → calls the Python server → Python talks to Google Calendar
       ↓
AI responds with the result
```

## What You'll Need

Before starting, make sure you have accounts/access to:

| Requirement | What it's for | Where to get it |
|-------------|--------------|-----------------|
| **Python 3.10+** | Runs the API server | [python.org](https://www.python.org/downloads/) |
| **n8n instance** | Hosts the AI workflow | [n8n.io](https://n8n.io/) (free cloud tier available) |
| **Google Cloud project** | Gives the bot permission to access your calendar | [console.cloud.google.com](https://console.cloud.google.com/) |
| **OpenAI API key** | Powers the AI (GPT-4.1) | [platform.openai.com](https://platform.openai.com/) |
| **ngrok** (local only) | Makes your local server reachable from the internet | [ngrok.com](https://ngrok.com/) (free tier works) |

## Setup Guide

### Step 1: Download the code

```bash
git clone https://github.com/elnino-hub/booking-agent.git
cd booking-agent
pip install -r requirements.txt
```

### Step 2: Get Google Calendar access

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** (top bar) → **New Project** → give it any name → **Create**
3. In the left sidebar: **APIs & Services** → **Library**
4. Search for **Google Calendar API** → click it → **Enable**
5. In the left sidebar: **APIs & Services** → **Credentials**
6. Click **+ Create Credentials** → **OAuth client ID**
7. If asked to configure a consent screen: choose **External**, fill in the app name (anything), your email, and save
8. Back in Credentials: **+ Create Credentials** → **OAuth client ID** → Application type: **Desktop app** → **Create**
9. Click **Download JSON** on the popup
10. Rename the downloaded file to `credentials.json` and move it into the `booking-agent` folder

### Step 3: Get an OpenAI API key

1. Go to [platform.openai.com](https://platform.openai.com/)
2. Sign up or log in
3. Go to **API Keys** → **Create new secret key**
4. Copy the key — you'll paste it into n8n later

### Step 4: Set up your environment file

```bash
cp .env.example .env
```

The defaults work for local development. No need to edit anything yet.

### Step 5: Start the Python server

```bash
uvicorn execution.api:app --host 0.0.0.0 --port 8000
```

**First time only:** A browser window will open asking you to sign in to Google and allow calendar access. Click **Allow**. After this, a `token.json` file is created and you won't be asked again.

You should see output like:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 6: Make your server reachable with ngrok

Open a **new terminal** (keep the Python server running in the old one) and run:

```bash
ngrok http 8000
```

You'll see something like:
```
Forwarding  https://abc123-def456.ngrok-free.dev → http://localhost:8000
```

**Copy that `https://...ngrok-free.dev` URL** — you'll need it in the next step.

### Step 7: Set up the n8n workflow

1. Log in to your [n8n instance](https://app.n8n.cloud/)
2. Go to **Workflows** → click **⋮** (three dots) → **Import from File**
3. Select the file `n8n/booking_workflow_template.json` from this project
4. You'll see a workflow with several nodes. Now you need to replace the placeholder URL:
   - Click on each of these nodes one by one: **Save User Message**, **Get History**, **CheckAvailability**, **BookAppointment**, **CancelAppointment**, **RescheduleAppointment**, **Save Agent Response**
   - In each one, find the URL field that says `YOUR_API_URL/...`
   - Replace `YOUR_API_URL` with your ngrok URL (e.g., `https://abc123-def456.ngrok-free.dev`)
   - Keep the path after it (e.g., `/calendar/events`, `/history/add`, etc.)
5. Click on the **OpenAI Chat Model** node → click **Create New Credential** → paste your OpenAI API key
6. Click **Save** (top right)
7. Toggle the workflow to **Active** (top right switch)
8. Click the **Chat Trigger** node → click **Open Chat** to test

Type something like "What's on my calendar this week?" — the bot should respond with your actual events.

## Cloud Deployment (Optional)

The setup above requires your computer to be running. For a persistent deployment:

### 1. Generate a cloud-ready auth token

```bash
python execution/auth_setup.py
```

This opens a browser for Google auth, then prints a long string of characters. Copy it.

### 2. Deploy to Railway

1. Push this repo to your own GitHub account
2. Go to [Railway](https://railway.com) → **New Project** → **Deploy from GitHub Repo**
3. Select your repo
4. Go to **Variables** and add:
   - `GOOGLE_TOKEN_B64` = the long string from step 1
   - `GOOGLE_APPLICATION_CREDENTIALS` = `credentials.json`
   - `PORT` = `8000`
   - `DB_PATH` = `history.db`

### 3. Update n8n URLs

Once Railway gives you a deployment URL (e.g., `https://booking-agent-production.up.railway.app`), go back to your n8n workflow and replace the ngrok URLs with this Railway URL. Now it runs 24/7 without your computer.

## Project Structure

```
booking-agent/
├── execution/               # The Python server and its components
│   ├── api.py               # Server entry point (all the API endpoints)
│   ├── calendar_client.py   # Connects to Google Calendar
│   ├── history_manager.py   # Stores conversation history (SQLite)
│   ├── auth_setup.py        # Helper for cloud deployment auth
│   ├── test_agent.py        # Automated test suite
│   └── test_setup.py        # Quick setup verification
├── directives/              # Instructions that define how the agent behaves
│   └── booking_agent.md
├── n8n/                     # n8n workflow file
│   ├── booking_workflow_template.json  ← import this into n8n
│   └── n8n_guide.md
├── .env.example             # Template for environment variables
├── railway.json             # Cloud deployment config
├── requirements.txt         # Python dependencies
└── README.md
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Browser doesn't open on first run | Make sure you're running the server locally (not on a remote machine). Delete `token.json` and try again. |
| n8n says "connection refused" | Check that your Python server is running AND ngrok is active. The ngrok URL changes every time you restart it — update n8n if it changed. |
| Bot says "I don't have access to your calendar" | This shouldn't happen — the bot is designed to always check. Try asking again. If it persists, restart the Python server. |
| Google auth fails | Make sure Calendar API is enabled in your Google Cloud project. Delete `token.json` and `credentials.json`, re-download credentials, and try again. |
| Bot books without checking conflicts | The AI prompt instructs it to check first, but AI isn't perfect. For critical use, always verify in Google Calendar. |

## License

MIT
