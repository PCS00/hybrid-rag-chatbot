from dotenv import load_dotenv
import os

load_dotenv()

from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

embedding = OpenAIEmbeddings()

vectorstore = Chroma(
    persist_directory="data",
    embedding_function=embedding
)


def add_documents(docs):

    vectorstore.add_texts(docs)
    vectorstore.persist()


def search_docs(query):

    results = vectorstore.similarity_search(query, k=3)

    return [doc.page_content for doc in results]