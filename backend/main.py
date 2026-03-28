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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


pending_booking = {}
conversation_state = {}


# -------------------------------
# FALLBACK
# -------------------------------
def fallback_response(message):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful clinic assistant."},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content


# -------------------------------
# USER INFO
# -------------------------------
def extract_user_info(message):
    email_match = re.search(r'\S+@\S+', message)

    if not email_match:
        return None, None

    email = email_match.group(0)
    name = message.replace(email, "").replace(",", "").strip()

    if len(name) < 2:
        return None, None

    return name, email


# -------------------------------
# CHAT
# -------------------------------
@app.post("/chat")
def chat(request: ChatRequest):

    message = request.message.strip()

    if not message:
        return {"reply": "Could you please clarify your request?"}

    # --------------------------------
    # EMAIL STEP (ONLY IF EMAIL PRESENT)
    # --------------------------------
    if pending_booking and "@" in message:

        name, email = extract_user_info(message)

        if not name or not email:
            return {"reply": "Please provide a valid name and email 😊"}

        reply = schedule(
            pending_booking["doctor"],
            pending_booking["day"],
            pending_booking["time"],
            name,
            email
        )

        if "confirmed" in reply.lower():
            pending_booking.clear()
            conversation_state.clear()
        else:
            return {"reply": reply}

        return {"reply": reply}

    # --------------------------------
    # CLASSIFY INTENT
    # --------------------------------
    intent = classify_intent(message)

    # --------------------------------
    # KNOWLEDGE
    # --------------------------------
    if intent == "knowledge":
        reply = rag_answer(message)

        if not reply or "i don't have" in reply.lower():
            reply = fallback_response(message)

        return {"reply": reply}

    # --------------------------------
    # ENTITY EXTRACTION
    # --------------------------------
    entities = extract_entities(message)

    doctor = entities.get("doctor")
    day = entities.get("day")
    time = entities.get("time")

    # restore context
    doctor = doctor or conversation_state.get("doctor")
    day = day or conversation_state.get("day")
    time = time or conversation_state.get("time")

    # save context
    if doctor:
        conversation_state["doctor"] = doctor
    if day:
        conversation_state["day"] = day
    if time:
        conversation_state["time"] = time

    # --------------------------------
    # AVAILABILITY
    # --------------------------------
    if intent == "availability":

        if not doctor:
            return {"reply": "Which doctor would you like to check?"}

        return {"reply": check_availability(doctor)}

    # --------------------------------
    # SCHEDULE
    # --------------------------------
    if intent == "schedule":

        if not doctor:
            return {"reply": "Which doctor would you like to book with?"}

        if not day or not time:
            return {"reply": check_availability(doctor)}

        pending_booking["doctor"] = doctor
        pending_booking["day"] = day
        pending_booking["time"] = time

        return {
            "reply": "Got it! Please provide your name and email to confirm the booking 📧"
        }

    # --------------------------------
    # CANCEL
    # --------------------------------
    if intent == "cancel":

        if not doctor or not day or not time:
            return {"reply": "Please specify doctor, day and time."}

        return {"reply": cancel(doctor, day, time)}

    # --------------------------------
    # FINAL FALLBACK
    # --------------------------------
    pending_booking.clear()
    return {"reply": fallback_response(message)}