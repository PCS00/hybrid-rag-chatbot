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

    return response.choices[0].message.content.strip().lower()