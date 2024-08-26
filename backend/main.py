import os
import uuid
import psycopg2

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Response, HTTPException, status
from fastapi.websockets import WebSocket
from fastapi.templating import Jinja2Templates


load_dotenv()

POSTGRES_NAME = os.getenv('POSTGRES_NAME')
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_HOST = os.getenv('POSTGRES_HOST')
POSTGRES_PORT = os.getenv('POSTGRES_PORT')

app = FastAPI()

faces = []
clients = []
templates = Jinja2Templates(directory="templates")


def open_conn():
    try:
        connection = psycopg2.connect(
            dbname=POSTGRES_NAME,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT
        )
        return connection
    except psycopg2.Error as e:
        raise e


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        clients.remove(websocket)


async def notify_clients(face_id: str):
    for client in clients:
        await client.send_text(face_id)


@app.get("/faces/{face_id}")
async def get_face(face_id: str):
    try:
        with open_conn() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT img FROM faces WHERE id = %s",
                               (face_id,))
                face = cursor.fetchone()

                if face is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                        detail='Face not found')

                img_data = face[0]

                if img_data is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                        detail='Face image data is empty')

                img_bytes = bytes(img_data)
                return Response(content=img_bytes, media_type="image/jpeg")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to retrieve face'
        )


@app.get("/faces")
async def get_last_five_faces():
    try:
        with open_conn() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id FROM faces ORDER BY id DESC LIMIT 5")
                faces = cursor.fetchall()

                return [{'id': face[0]} for face in faces]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to retrieve faces'
        )


@app.post("/upload_face")
async def load_face(file: UploadFile = File(...)):
    face_id = str(uuid.uuid4())
    face_file = await file.read()

    try:
        with open_conn() as connection:
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO faces (id, img) VALUES (%s, %s)",
                               (face_id, psycopg2.Binary(face_file)))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to upload face'
        )

    await notify_clients(face_id)
    return {'face_id': face_id}
