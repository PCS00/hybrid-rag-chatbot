import pandas as pd
import io
import os
import json
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials

import yagmail


# --------------------------------
# GOOGLE CONFIG
# --------------------------------
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar"
]

creds_json = json.loads(os.getenv("GOOGLE_CREDENTIALS"))

creds = Credentials.from_service_account_info(
    creds_json,
    scopes=SCOPES
)

drive_service = build("drive", "v3", credentials=creds)
calendar_service = build("calendar", "v3", credentials=creds)

CALENDAR_ID = "primary"


# --------------------------------
# EMAIL CONFIG
# --------------------------------
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")


def send_email(to_email, name, doctor, day, time, link):
    try:
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

    except Exception as e:
        print("Email failed:", str(e))


# --------------------------------
# LOAD EXCEL FROM DRIVE
# --------------------------------
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


# --------------------------------
# SAVE EXCEL
# --------------------------------
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


# --------------------------------
# CREATE CALENDAR EVENT
# --------------------------------
def create_calendar_event(doctor, day, time, name, email):

    try:
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

    except Exception as e:
        print("Calendar error:", str(e))
        return "Calendar link unavailable"


# --------------------------------
# CHECK AVAILABILITY
# --------------------------------
def check_availability(doctor):

    df, _ = load_excel()

    doctor = doctor.lower().strip()

    available = df[
        df["Consultant"].astype(str).str.lower().str.contains(doctor) &
        (df["Available"].astype(str).str.lower() == "yes")
    ]

    if available.empty:
        return f"{doctor.title()} has no available appointments."

    response = f"{doctor.title()} is available at:\n"

    for _, row in available.iterrows():
        response += f"- {row['Day']} at {row['Time']}\n"

    return response


# --------------------------------
# SCHEDULE APPOINTMENT
# --------------------------------
def schedule(doctor, day, time, name, email):

    df, file_id = load_excel()

    doctor = doctor.lower().strip()
    day = day.lower().strip()
    time = normalize_time(time)

    df["Consultant"] = df["Consultant"].astype(str)
    df["Day"] = df["Day"].astype(str)
    df["Time"] = df["Time"].astype(str)

    match = df[
        df["Consultant"].str.lower().str.contains(doctor) &
        df["Day"].str.lower().str.contains(day) &
        (df["Time"].str.upper() == time.upper()) &
        (df["Available"].str.lower() == "yes")
    ]

    if match.empty:
        return f"That slot is not available.\n\n{check_availability(doctor)}"

    index = match.index[0]

    df.at[index, "Available"] = "No"
    df.at[index, "Name"] = name
    df.at[index, "Email"] = email

    save_excel(df, file_id)

    # Use original formatted values from sheet
    booked_doctor = df.at[index, "Consultant"]
    booked_day = df.at[index, "Day"]
    booked_time = df.at[index, "Time"]

    calendar_link = create_calendar_event(
        booked_doctor, booked_day, booked_time, name, email
    )

    send_email(email, name, booked_doctor, booked_day, booked_time, calendar_link)

    return f"""
✅ Appointment confirmed!

Doctor: {booked_doctor}
Day: {booked_day}
Time: {booked_time}

📅 Calendar:
{calendar_link}
"""

def normalize_time(t):
    t = t.lower().replace(".", "").strip()

    if "am" in t or "pm" in t:
        try:
            return datetime.strptime(t, "%I %p").strftime("%I:%M %p")
        except:
            try:
                return datetime.strptime(t, "%I:%M %p").strftime("%I:%M %p")
            except:
                return t.upper()
    return t.upper()

# --------------------------------
# CANCEL APPOINTMENT
# --------------------------------
def cancel(doctor, day, time):

    df, file_id = load_excel()

    doctor = doctor.lower().strip()
    day = day.lower().strip()
    time = time.lower().strip()

    match = df[
        df["Consultant"].astype(str).str.lower().str.contains(doctor) &
        df["Day"].astype(str).str.lower().str.contains(day) &
        df["Time"].astype(str).str.lower().str.contains(time) &
        (df["Available"].astype(str).str.lower() == "no")
    ]

    if match.empty:
        return "Appointment not found."

    index = match.index[0]

    df.at[index, "Available"] = "Yes"
    df.at[index, "Name"] = ""
    df.at[index, "Email"] = ""

    save_excel(df, file_id)

    return f"❌ Appointment cancelled for {doctor.title()} on {day.title()} at {time}."