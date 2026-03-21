from openai import OpenAI
from vector_db import search_docs

client = OpenAI()


def rag_answer(question):

    docs = search_docs(question)

    context = "\n".join(docs)

    prompt = f"""
You are a helpful clinic assistant.

Answer ONLY using the information in the context.
If the answer is not in the context say:
"I don't have that information."

Context:
{context}

Question:
{question}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content