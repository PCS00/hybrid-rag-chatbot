from drive_loader import load_drive_files
from vector_db import add_documents


def build_vector_database():

    print("Loading files from Google Drive...")

    docs = load_drive_files()

    print(f"{len(docs)} documents loaded")

    add_documents(docs)

    print("Vector database built successfully!")


if __name__ == "__main__":
    build_vector_database()