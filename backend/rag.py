from openai import OpenAI
from backend.vector_db import search_docs

client = OpenAI()


def rag_answer(question):

    docs = search_docs(question)
    context = "\n".join(docs)

    prompt = f"""
You are a friendly and helpful clinic assistant.

Use the context below if relevant.
If the context is not helpful, answer naturally using your own knowledge.

Keep answers conversational and helpful.

Context:
{context}

User question:
{question}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content.strip()