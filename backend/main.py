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


# -------------------------------
# FALLBACK RESPONSE
# -------------------------------
def fallback_response(message):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a friendly clinic assistant."},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content


# -------------------------------
# EXTRACT USER INFO
# -------------------------------
def extract_user_info(message):
    email_match = re.search(r'\S+@\S+', message)

    if not email_match:
        return None, None

    email = email_match.group(0)
    name = message.replace(email, "").strip()

    return name, email


# -------------------------------
# CHAT ENDPOINT
# -------------------------------
@app.post("/chat")
def chat(request: ChatRequest):

    message = request.message

    # --------------------------------
    # STEP 1: USER PROVIDES NAME + EMAIL
    # --------------------------------
    if pending_booking:

        name, email = extract_user_info(message)

        if not name or not email:
            return {"reply": "Please provide your name and email 😊"}

        reply = schedule(
            pending_booking["doctor"],
            pending_booking["day"],
            pending_booking["time"],
            name,
            email
        )

        pending_booking.clear()

        return {"reply": reply}

    # --------------------------------
    # STEP 2: CLASSIFY INTENT
    # --------------------------------
    intent = classify_intent(message)

    # --------------------------------
    # STEP 3: KNOWLEDGE (RAG + FALLBACK)
    # --------------------------------
    if intent == "knowledge":

        reply = rag_answer(message)

        if not reply or "i don't have" in reply.lower():
            reply = fallback_response(message)

        return {"reply": reply}

    # --------------------------------
    # STEP 4: EXTRACT ENTITIES
    # --------------------------------
    entities = extract_entities(message)

    doctor = entities.get("doctor")
    day = entities.get("day")
    time = entities.get("time")

    # --------------------------------
    # STEP 5: AVAILABILITY
    # --------------------------------
    if intent == "availability":

        if not doctor:
            return {"reply": "Please tell me which doctor you're asking about 😊"}

        return {"reply": check_availability(doctor)}

    # --------------------------------
    # STEP 6: SCHEDULE
    # --------------------------------
    if intent == "schedule":

        if not doctor or not day or not time:
            return {
                "reply": "Sure! Please tell me the doctor, day, and time you'd like to book 😊"
            }

        pending_booking["doctor"] = doctor
        pending_booking["day"] = day
        pending_booking["time"] = time

        return {
            "reply": "Got it! Please provide your name and email to confirm the booking 📧"
        }

    # --------------------------------
    # STEP 7: CANCEL
    # --------------------------------
    if intent == "cancel":

        if not doctor or not day or not time:
            return {"reply": "Please specify doctor, day and time."}

        return {"reply": cancel(doctor, day, time)}

    # --------------------------------
    # FINAL FALLBACK (NEVER CRASH)
    # --------------------------------
    return {"reply": fallback_response(message)}