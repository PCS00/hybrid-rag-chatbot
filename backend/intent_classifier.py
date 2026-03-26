from openai import OpenAI

client = OpenAI()


def classify_intent(question):

    prompt = f"""
Classify the user request.

Categories:
knowledge
schedule
cancel
availability

Question: {question}

Return only the category.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    intent = response.choices[0].message.content.strip().lower()

    if "schedule" in intent or "book" in intent:
        return "schedule"
    if "cancel" in intent:
        return "cancel"
    if "availability" in intent:
        return "availability"

    return "knowledge"