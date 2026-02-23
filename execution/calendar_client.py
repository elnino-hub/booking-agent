import os
import base64
import datetime
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']

CREDENTIALS_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
TOKEN_FILE = 'token.json'


def _load_token_from_b64():
    """Decode GOOGLE_TOKEN_B64 env var into a credentials object."""
    b64 = os.getenv("GOOGLE_TOKEN_B64")
    if not b64:
        return None
    raw = base64.b64decode(b64)
    return pickle.loads(raw)


def authenticate():
    creds = None

    # Priority 1: base64-encoded token (cloud / headless deploys)
    creds = _load_token_from_b64()

    # Priority 2: local token.json file
    if creds is None and os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Credentials file '{CREDENTIALS_FILE}' not found. "
                    "For local dev, place credentials.json in the project root. "
                    "For cloud deploy, set GOOGLE_TOKEN_B64 (run: python execution/auth_setup.py)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Persist locally (skip if running headless with no writable token file)
        try:
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
        except OSError:
            pass  # read-only filesystem on some cloud hosts

    return build('calendar', 'v3', credentials=creds)

def list_upcoming_events(max_results=10):
    """Lists upcoming events."""
    service = authenticate()
    now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    
    events_result = service.events().list(
        calendarId='primary', timeMin=now,
        maxResults=max_results, singleEvents=True,
        orderBy='startTime').execute()
    events = events_result.get('items', [])
    return events

def create_event(summary, start_time_iso, end_time_iso, description="", attendee_emails=None):
    """Creates a new event with optional attendees and Google Meet link."""
    import json as json_module

    service = authenticate()
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time_iso,
            'timeZone': 'UTC', # Adjust if needed, or pass in args
        },
        'end': {
            'dateTime': end_time_iso,
            'timeZone': 'UTC',
        },
        'conferenceData': {
            'createRequest': {
                'requestId': f"meet-{datetime.datetime.now().timestamp()}",
                'conferenceSolutionKey': {'type': 'hangoutsMeet'}
            }
        }
    }

    # Add attendees if provided
    if attendee_emails:
        # Handle if AI sends JSON string instead of array
        if isinstance(attendee_emails, str):
            try:
                # Try to parse as JSON array first
                attendee_emails = json_module.loads(attendee_emails)
            except (json_module.JSONDecodeError, ValueError):
                # If not JSON, treat as single email
                attendee_emails = [attendee_emails]
        event['attendees'] = [{'email': email} for email in attendee_emails]
        print(f"[DEBUG] Adding attendees to event: {event['attendees']}")

    print(f"[DEBUG] Sending event to Google Calendar API:")
    print(json_module.dumps(event, indent=2))

    created_event = service.events().insert(
        calendarId='primary',
        body=event,
        conferenceDataVersion=1,
        sendUpdates='all'  # Send invitations to all attendees
    ).execute()

    print(f"[DEBUG] Google Calendar API response:")
    print(json_module.dumps(created_event, indent=2, default=str))

    return created_event

def cancel_event(event_id):
    """Cancels an event by ID."""
    service = authenticate()
    service.events().delete(calendarId='primary', eventId=event_id).execute()
    return True

def update_event(event_id, summary=None, start_time_iso=None, end_time_iso=None, description=None):
    """Updates an existing event. Only provided fields will be updated."""
    service = authenticate()
    
    # Get the existing event first
    event = service.events().get(calendarId='primary', eventId=event_id).execute()
    
    # Update only the provided fields
    if summary is not None:
        event['summary'] = summary
    if description is not None:
        event['description'] = description
    if start_time_iso is not None:
        event['start'] = {
            'dateTime': start_time_iso,
            'timeZone': event['start'].get('timeZone', 'UTC'),
        }
    if end_time_iso is not None:
        event['end'] = {
            'dateTime': end_time_iso,
            'timeZone': event['end'].get('timeZone', 'UTC'),
        }
    
    updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
    return updated_event

if __name__ == "__main__":
    print("Testing Calendar Client...")
    try:
        events = list_upcoming_events(3)
        if not events:
            print("No upcoming events found.")
        else:
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                print(start, event['summary'])
    except Exception as e:
        print(f"Error: {e}")
