from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from datetime import datetime

SCOPES = ["https://www.googleapis.com/auth/calendar"]

creds = Credentials.from_service_account_file(
    "credentials.json",
    scopes=SCOPES
)

service = build("calendar", "v3", credentials=creds)

CALENDAR_ID = "primary"


def create_event(doctor, day, time, name, email):

    start_time = f"{day} {time}"
    
    event = {
        "summary": f"Appointment with {doctor}",
        "description": f"Patient: {name}",
        "start": {
            "dateTime": start_time,
            "timeZone": "Asia/Kolkata"
        },
        "end": {
            "dateTime": start_time,
            "timeZone": "Asia/Kolkata"
        },
        "attendees": [
            {"email": email}
        ]
    }

    event = service.events().insert(
        calendarId=CALENDAR_ID,
        body=event
    ).execute()

    return event.get("htmlLink")