import pandas as pd
import io
import os
import json
import traceback
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials

import yagmail


# -------------------------------
# CONFIG
# -------------------------------
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

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")


# -------------------------------
# HELPERS
# -------------------------------
def normalize_text(text):
    return text.lower().replace(".", "").replace("dr", "").strip()


def normalize_time(t):
    t = t.lower().replace(".", "").strip()

    try:
        return datetime.strptime(t, "%I:%M %p").strftime("%I:%M %p")
    except:
        try:
            return datetime.strptime(t, "%I %p").strftime("%I:%M %p")
        except:
            return t.upper()


# -------------------------------
# EMAIL
# -------------------------------
def send_email(to_email, name, doctor, day, time, link):
    try:
        yag = yagmail.SMTP(EMAIL_USER, EMAIL_PASS)

        yag.send(
            to=to_email,
            subject="Appointment Confirmation",
            contents=f"""
Hi {name},

Your appointment is confirmed!

Doctor: {doctor}
Day: {day}
Time: {time}

Link:
{link}
"""
        )
    except Exception as e:
        print("Email error:", e)


# -------------------------------
# LOAD/SAVE EXCEL
# -------------------------------
def load_excel():
    results = drive_service.files().list(
        q="name='appointments.xlsx'",
        fields="files(id,name)"
    ).execute()

    file_id = results["files"][0]["id"]

    data = drive_service.files().get_media(fileId=file_id).execute()

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

    drive_service.files().update(fileId=file_id, media_body=media).execute()


# -------------------------------
# AVAILABILITY
# -------------------------------
def check_availability(doctor):

    df, _ = load_excel()

    doctor = normalize_text(doctor)

    available = df[
        df["Consultant"].astype(str).apply(lambda x: normalize_text(x)).str.contains(doctor) &
        (df["Available"].astype(str).str.lower() == "yes")
    ]

    if available.empty:
        return f"{doctor.title()} has no available appointments."

    response = f"{doctor.title()} is available at:\n"

    for _, row in available.iterrows():
        response += f"- {row['Day']} at {row['Time']}\n"

    return response


# -------------------------------
# SCHEDULE
# -------------------------------
def schedule(doctor, day, time, name, email):

    try:
        df, file_id = load_excel()

        doctor_norm = normalize_text(doctor)
        day = day.lower().strip()
        time_norm = normalize_time(time)

        match = df[
            df["Consultant"].astype(str).apply(lambda x: normalize_text(x)).str.contains(doctor_norm) &
            df["Day"].str.lower().str.contains(day) &
            (df["Time"].str.upper() == time_norm.upper()) &
            (df["Available"].str.lower() == "yes")
        ]

        if match.empty:
            return f"That slot is not available.\n\n{check_availability(doctor)}"

        index = match.index[0]

        df.at[index, "Available"] = "No"
        df.at[index, "Name"] = name
        df.at[index, "Email"] = email

        save_excel(df, file_id)

        booked_doctor = df.at[index, "Consultant"]
        booked_day = df.at[index, "Day"]
        booked_time = df.at[index, "Time"]

        calendar_link = "Calendar link here"  # optional

        send_email(email, name, booked_doctor, booked_day, booked_time, calendar_link)

        return f"""
✅ Appointment confirmed!

Doctor: {booked_doctor}
Day: {booked_day}
Time: {booked_time}
"""

    except Exception:
        traceback.print_exc()
        return "Something went wrong while booking. Please try again."


# -------------------------------
# CANCEL
# -------------------------------
def cancel(doctor, day, time):

    df, file_id = load_excel()

    doctor = normalize_text(doctor)
    day = day.lower().strip()
    time = normalize_time(time)

    match = df[
        df["Consultant"].astype(str).apply(lambda x: normalize_text(x)).str.contains(doctor) &
        df["Day"].str.lower().str.contains(day) &
        (df["Time"].str.upper() == time.upper()) &
        (df["Available"].str.lower() == "no")
    ]

    if match.empty:
        return "Appointment not found."

    index = match.index[0]

    df.at[index, "Available"] = "Yes"
    df.at[index, "Name"] = ""
    df.at[index, "Email"] = ""

    save_excel(df, file_id)

    return "Appointment cancelled successfully."