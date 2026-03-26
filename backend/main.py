from fastapi import FastAPI
from pydantic import BaseModel
import re
from fastapi.middleware.cors import CORSMiddleware
from backend.rag import rag_answer
from backend.scheduler import schedule, cancel, check_availability
from backend.intent_classifier import classify_intent
from backend.entity_extractor import extract_entities
from openai import OpenAI
client = OpenAI()

def fallback_response(message):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a friendly clinic assistant."},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (for testing)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


pending_booking = {}


def extract_user_info(message):

    email_match = re.search(r'\S+@\S+', message)

    if not email_match:
        return None, None

    email = email_match.group(0)
    name = message.replace(email, "").strip()

    return name, email


@app.post("/chat")
def chat(request: ChatRequest):

    message = request.message

    # --------------------------------
    # USER PROVIDING NAME + EMAIL
    # --------------------------------

    if pending_booking:

        name, email = extract_user_info(message)

        if not name or not email:
            return {"reply": "Please provide your name and email."}

        reply = schedule(
            pending_booking["doctor"],
            pending_booking["day"],
            pending_booking["time"],
            name,
            email
        )

        pending_booking.clear()

        # --------------------------------
        # DEFAULT FALLBACK (VERY IMPORTANT)
        # --------------------------------

        return {"reply": fallback_response(message)}

    # --------------------------------
    # CLASSIFY INTENT
    # --------------------------------

    intent = classify_intent(message)

    if intent == "knowledge":
        reply = rag_answer(message)

        if not reply or "i don't have" in reply.lower():
            reply = fallback_response(message)

    return {"reply": reply}

    entities = extract_entities(message)

    doctor = entities.get("doctor")
    day = entities.get("day")
    time = entities.get("time")

    # --------------------------------
    # AVAILABILITY
    # --------------------------------

    if intent == "availability":

        if not doctor:
            return {"reply": "Please specify the doctor."}

        return {"reply": check_availability(doctor)}

    # --------------------------------
    # SCHEDULE
    # --------------------------------

    if intent == "schedule":

        if not doctor or not day or not time:
            return {"reply": "Please specify doctor, day and time."}

        pending_booking["doctor"] = doctor
        pending_booking["day"] = day
        pending_booking["time"] = time

        return {"reply": "Please provide your name and email to confirm the booking."}

    # --------------------------------
    # CANCEL
    # --------------------------------

    if intent == "cancel":

        if not doctor or not day or not time:
            return {"reply": "Please specify doctor, day and time."}

        return {"reply": cancel(doctor, day, time)}

    return {"reply": "Sorry, I didn't understand your request."}