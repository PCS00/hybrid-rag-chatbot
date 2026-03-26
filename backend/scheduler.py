import pandas as pd
import io
import yagmail

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar"
]

import os
import json

creds_json = json.loads(os.getenv("GOOGLE_CREDENTIALS"))

creds = Credentials.from_service_account_info(
    creds_json,
    scopes=SCOPES
)

drive_service = build("drive", "v3", credentials=creds)
calendar_service = build("calendar", "v3", credentials=creds)

CALENDAR_ID = "primary"

def send_email(to_email, name, doctor, day, time, link):

    

    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASS = os.getenv("EMAIL_PASS")

    yag = yagmail.SMTP(EMAIL_USER, EMAIL_PASS)

    subject = "Appointment Confirmation"

    content = f"""
Hi {name},

Your appointment has been successfully booked!

Doctor: {doctor}
Date: {day}
Time: {time}

Calendar Link:
{link}

Thank you 😊
"""

    yag.send(to=to_email, subject=subject, contents=content)


def load_excel():

    results = drive_service.files().list(
        q="name='appointments.xlsx'",
        fields="files(id,name)"
    ).execute()

    files = results.get("files", [])

    if not files:
        raise Exception("appointments.xlsx not found")

    file_id = files[0]["id"]

    request = drive_service.files().get_media(fileId=file_id)
    data = request.execute()

    df = pd.read_excel(io.BytesIO(data))

    return df, file_id


def save_excel(df, file_id):

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    media = MediaIoBaseUpload(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    drive_service.files().update(
        fileId=file_id,
        media_body=media
    ).execute()

from datetime import datetime, timedelta


def create_calendar_event(doctor, day, time, name, email):

    # Convert to datetime
    start = datetime.strptime(f"{day} {time}", "%A %I:%M %p")

    end = start + timedelta(hours=1)

    event = {
        "summary": f"Appointment with {doctor}",
        "description": f"Patient: {name} ({email})",
        "start": {
            "dateTime": start.isoformat(),
            "timeZone": "Asia/Kolkata"
        },
        "end": {
            "dateTime": end.isoformat(),
            "timeZone": "Asia/Kolkata"
        }
    }

    event = calendar_service.events().insert(
        calendarId=CALENDAR_ID,
        body=event
    ).execute()

    return event.get("htmlLink")


def check_availability(doctor):

    df, _ = load_excel()

    available = df[
        (df["Consultant"].astype(str).str.lower().str.contains(doctor.lower())) &
        (df["Available"].astype(str).str.lower() == "yes")
    ]

    if available.empty:
        return f"{doctor} has no available appointments."

    response = f"{doctor} is available at:\n"

    for _, row in available.iterrows():
        response += f"- {row['Day']} at {row['Time']}\n"

    return response


def schedule(doctor, day, time, name, email):

    df, file_id = load_excel()

    match = df[
        (df["Consultant"] == doctor)
        & (df["Day"] == day)
        & (df["Time"] == time)
        & (df["Available"] == "Yes")
    ]

    if match.empty:
        return "That slot is not available."

    index = match.index[0]

    df.at[index, "Available"] = "No"
    df.at[index, "Name"] = name
    df.at[index, "Email"] = email

    save_excel(df, file_id)

    calendar_link = create_calendar_event(
        doctor, day, time, name, email
    )
    send_email(email, name, doctor, day, time, calendar_link)

    return f"""
Appointment confirmed!

Doctor: {doctor}
Day: {day}
Time: {time}

Calendar Event:
{calendar_link}
"""


def cancel(doctor, day, time):

    df, file_id = load_excel()

    match = df[
        (df["Consultant"] == doctor)
        & (df["Day"] == day)
        & (df["Time"] == time)
        & (df["Available"] == "No")
    ]

    if match.empty:
        return "Appointment not found."

    index = match.index[0]

    df.at[index, "Available"] = "Yes"
    df.at[index, "Name"] = ""
    df.at[index, "Email"] = ""

    save_excel(df, file_id)

    return f"Appointment with {doctor} on {day} at {time} cancelled."
