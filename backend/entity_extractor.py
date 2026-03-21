from openai import OpenAI
import json

client = OpenAI()


def extract_entities(message):

    prompt = f"""
Extract doctor, day, and time from the message.

Return JSON in this format:

{{
 "doctor": "...",
 "day": "...",
 "time": "..."
}}

If a value is missing return null.

Message:
{message}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    content = response.choices[0].message.content.strip()

    content = content.replace("```json", "").replace("```", "")

    try:
        data = json.loads(content)
    except:
        data = {"doctor": None, "day": None, "time": None}

    return data