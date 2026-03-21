from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import pandas as pd
import io

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

creds = Credentials.from_service_account_file(
    "credentials.json",
    scopes=SCOPES
)

service = build("drive", "v3", credentials=creds)


def load_drive_files():

    docs = []

    results = service.files().list(
        pageSize=20,
        fields="files(id, name, mimeType)"
    ).execute()

    files = results.get("files", [])

    for file in files:

        name = file["name"]
        file_id = file["id"]

        if name.endswith(".txt"):

            request = service.files().get_media(fileId=file_id)
            content = request.execute().decode("utf-8")

            docs.append(content)

        if name.endswith(".xlsx"):

            request = service.files().get_media(fileId=file_id)
            data = request.execute()

            df = pd.read_excel(io.BytesIO(data))

            for _, row in df.iterrows():
                row_text = " ".join(map(str, row))
                docs.append(row_text)

    return docs