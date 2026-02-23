from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
import json

# Import our tools
from execution import history_manager
from execution import calendar_client

app = FastAPI(title="Booking Agent API")

class Message(BaseModel):
    user_id: str
    role: str
    content: str

class EventRequest(BaseModel):
    summary: str
    start_time: str # ISO format
    end_time: str   # ISO format
    description: Optional[str] = ""
    attendee_emails: Optional[List[str]] = None


class EventID(BaseModel):
    event_id: str

@app.get("/")
def read_root():
    return {"status": "running", "service": "Booking Agent API"}

# --- History Endpoints ---

@app.post("/history/add")
def add_history(msg: Message):
    try:
        history_manager.save_message(msg.user_id, msg.role, msg.content)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history/list")
def get_history(user_id: str, limit: int = 10):
    try:
        return history_manager.get_recent_history(user_id, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Calendar Endpoints ---

@app.get("/calendar/events")
def list_events(limit: int = 10):
    try:
        events = calendar_client.list_upcoming_events(limit)
        return events
    except FileNotFoundError:
         raise HTTPException(status_code=500, detail="Credentials not found. Server setup incomplete.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/calendar/book")
async def book_event(raw_body: dict):
    try:
        # Handle n8n's quirky format - data might be wrapped in "query"
        if "query" in raw_body:
            data = raw_body["query"]
        else:
            data = raw_body

        # Extract fields
        summary = data.get("summary")
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        description = data.get("description", "")
        attendee_emails = data.get("attendee_emails")

        # Handle attendee_emails - might be string, array, or JSON string
        if attendee_emails:
            if isinstance(attendee_emails, str):
                try:
                    attendee_emails = json.loads(attendee_emails)
                except (json.JSONDecodeError, ValueError):
                    attendee_emails = [attendee_emails]

        print(f"Received booking request:")
        print(f"  Summary: {summary}")
        print(f"  Attendees: {attendee_emails} (type: {type(attendee_emails)})")

        created_event = calendar_client.create_event(
            summary, start_time, end_time, description, attendee_emails
        )

        print(f"Event created successfully. ID: {created_event.get('id')}")
        print(f"  Meet link: {created_event.get('hangoutLink')}")
        print(f"  Attendees: {created_event.get('attendees')}")

        return created_event
    except Exception as e:
        print(f"Error creating event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/calendar/cancel")
def cancel_calendar_event(payload: EventID):
    try:
        calendar_client.cancel_event(payload.event_id)
        return {"status": "cancelled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RescheduleRequest(BaseModel):
    event_id: str
    summary: Optional[str] = None
    start_time: str
    end_time: str
    description: Optional[str] = None

@app.post("/calendar/reschedule")
def reschedule_event(payload: RescheduleRequest):
    try:
        updated_event = calendar_client.update_event(
            payload.event_id,
            summary=payload.summary if payload.summary else None,
            start_time_iso=payload.start_time,
            end_time_iso=payload.end_time,
            description=payload.description if payload.description else None
        )
        return updated_event
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"Starting API on {host}:{port}...")
    uvicorn.run(app, host=host, port=port)
