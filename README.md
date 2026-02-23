# Booking Agent

An AI-powered calendar assistant that books, reschedules, and cancels Google Calendar events through natural conversation. Built with n8n + FastAPI + GPT-4.1.

**What it does:** You chat with the agent, and it manages your Google Calendar — checking availability, detecting conflicts, booking meetings with Google Meet links, rescheduling, and cancelling.

## Architecture

```
User ──► n8n Chat Trigger ──► Save Message ──► Get History ──► AI Agent ──► Save Response
                                                                 │
                                                    ┌────────────┼────────────┐
                                                    ▼            ▼            ▼
                                              CheckAvail   Book/Cancel   Reschedule
                                                    │            │            │
                                                    └────────────┼────────────┘
                                                                 ▼
                                                          FastAPI Server
                                                                 │
                                                          Google Calendar
```

The project uses a **3-layer architecture**:
1. **Directives** (`directives/`) — SOPs that define what the agent should do
2. **Orchestration** (n8n AI Agent) — LLM decision-making and tool routing
3. **Execution** (`execution/`) — Deterministic Python scripts for API calls

## Quick Start (Local)

### Prerequisites
- Python 3.10+
- [n8n](https://n8n.io/) instance (cloud or self-hosted)
- Google Cloud project with Calendar API enabled
- OpenAI API key (for GPT-4.1 in n8n)

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/booking-agent.git
cd booking-agent
pip install -r requirements.txt
```

### 2. Set up Google Calendar credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use an existing one)
3. Enable the **Google Calendar API**
4. Go to **APIs & Services > Credentials > Create Credentials > OAuth client ID**
5. Application type: **Desktop app**
6. Download the JSON and save it as `credentials.json` in the project root

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env — the defaults work for local development
```

### 4. Run the API server

```bash
uvicorn execution.api:app --host 0.0.0.0 --port 8000
```

On first run, a browser window opens for Google Calendar authorization. After approving, a `token.json` is created automatically.

### 5. Expose with ngrok (for n8n to reach your local server)

```bash
ngrok http 8000
```

Copy the `https://...ngrok-free.dev` URL.

### 6. Import the n8n workflow

1. Open your n8n instance
2. Go to **Workflows > Import from File**
3. Select `n8n/booking_workflow_template.json`
4. **Find-and-replace** `YOUR_API_URL` with your ngrok URL in every HTTP Request node and tool node (6 places total)
5. Connect your **OpenAI credential** to the "OpenAI Chat Model" node
6. **Activate** the workflow
7. Open the Chat Trigger's built-in chat panel to test

## Cloud Deployment (Railway)

For a persistent deployment without ngrok:

### 1. Generate the auth token

```bash
python execution/auth_setup.py
```

This opens a browser for Google auth, then prints a base64 string.

### 2. Deploy to Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/template)

Or manually:
1. Push this repo to GitHub
2. Connect the repo in [Railway](https://railway.com)
3. Add these environment variables:
   - `GOOGLE_TOKEN_B64` — the base64 string from step 1
   - `GOOGLE_APPLICATION_CREDENTIALS` — `credentials.json`
   - `PORT` — `8000`
   - `DB_PATH` — `history.db`

### 3. Update n8n workflow URLs

Replace `YOUR_API_URL` with your Railway deployment URL (e.g., `https://booking-agent-production.up.railway.app`).

## API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Health check |
| GET | `/history/list` | Get conversation history |
| POST | `/history/add` | Save a message |
| GET | `/calendar/events` | List upcoming events |
| POST | `/calendar/book` | Book an appointment |
| POST | `/calendar/reschedule` | Reschedule an appointment |
| POST | `/calendar/cancel` | Cancel an appointment |

## Project Structure

```
booking-agent/
├── execution/
│   ├── api.py              # FastAPI server
│   ├── calendar_client.py  # Google Calendar API client
│   ├── history_manager.py  # SQLite conversation history
│   ├── auth_setup.py       # Token → base64 helper for cloud deploy
│   └── test_agent.py       # Integration test suite
├── directives/
│   └── booking_agent.md    # Agent SOP
├── n8n/
│   └── booking_workflow_template.json  # n8n workflow (import this)
├── .env.example
├── railway.json
├── requirements.txt
└── README.md
```

## How the Agent Works

The AI Agent (GPT-4.1 in n8n) follows strict tool-usage rules defined in its system prompt:

- **Availability questions** → always calls `CheckAvailability` (never answers from memory)
- **Booking** → checks for conflicts first, warns if a clash exists, only books after confirmation
- **Rescheduling** → looks up event ID, checks new slot for conflicts, then moves the event
- **Cancelling** → looks up event ID, confirms which event, then cancels

Conversation history is stored in SQLite and passed to the agent on each turn, giving it multi-turn memory.

## Testing

The integration test suite sends real prompts to the n8n chat endpoint and verifies which tool nodes actually fired via the n8n executions API:

```bash
python execution/test_agent.py
```

Requires the API server, ngrok tunnel, and n8n workflow to all be running. Tests create/cancel events with a `[TEST]` prefix on your real calendar.

## License

MIT
