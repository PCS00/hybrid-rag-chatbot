from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import os
import json

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Use environment variable (for Render)
creds_json = json.loads(os.getenv("GOOGLE_CREDENTIALS"))

creds = Credentials.from_service_account_info(
    creds_json,
    scopes=SCOPES
)

service = build("calendar", "v3", credentials=creds)

CALENDAR_ID = "primary"


# --------------------------------
# HELPER: Convert day + time → datetime
# --------------------------------
def get_next_datetime(day, time_str):

    day = day.strip().capitalize()
    time_str = time_str.strip().upper()

    # Parse time safely
    try:
        parsed_time = datetime.strptime(time_str, "%I:%M %p")
    except:
        parsed_time = datetime.strptime(time_str, "%I %p")

    # Today
    today = datetime.now()

    # Convert weekday name → number
    target_day = datetime.strptime(day, "%A").weekday()

    # Calculate next occurrence of that weekday
    days_ahead = target_day - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7

    appointment_date = today + timedelta(days=days_ahead)

    # Combine date + time
    final_datetime = appointment_date.replace(
        hour=parsed_time.hour,
        minute=parsed_time.minute,
        second=0,
        microsecond=0
    )

    return final_datetime


# --------------------------------
# CREATE EVENT
# --------------------------------
def create_event(doctor, day, time, name, email):

    try:
        start_dt = get_next_datetime(day, time)
        end_dt = start_dt + timedelta(hours=1)

        event = {
            "summary": f"Appointment with {doctor}",
            "description": f"Patient: {name}",
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "Asia/Kolkata"
            },
            "end": {
                "dateTime": end_dt.isoformat(),
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

    except Exception as e:
        print("Calendar error:", str(e))
        return "Calendar booking failed (but appointment is saved)"