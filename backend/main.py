import os
import uuid
import psycopg2
import logging

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Response, HTTPException, status, Request
from fastapi.websockets import WebSocket
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware


load_dotenv()

POSTGRES_NAME = os.getenv('POSTGRES_NAME')
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_HOST = os.getenv('POSTGRES_HOST')
POSTGRES_PORT = os.getenv('POSTGRES_PORT')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI()

clients = []
templates = Jinja2Templates(directory="../frontend/templates")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def open_conn():
    try:
        connection = psycopg2.connect(
            dbname=POSTGRES_NAME,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT
        )
        logger.info('Successfully connected to the database')
        return connection
    except psycopg2.Error as ex:
        logger.info(f'Failed to connect to the database: {ex}')
        raise ex


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)
    logger.info(
        f'WebSocket connection established with client {websocket.client}')

    try:
        while True:
            await websocket.receive_text()
    except Exception as ex:
        logger.error(f'WebSocket error: {ex}')
    finally:
        clients.remove(websocket)
        logger.info(
            f'WebSocket connection closed with client {websocket.client}')


async def notify_clients(face_id: str):
    for client in clients:
        await client.send_text(face_id)
        logger.info(f'Notified clients about new face ID: {face_id}')


@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/faces/{face_id}")
async def get_face(face_id: str):
    try:
        with open_conn() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT img FROM faces WHERE id = %s",
                               (face_id,))
                face = cursor.fetchone()

                if face is None:
                    logger.warning(f"Face ID {face_id} not found")
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                        detail='Face not found')

                img_data = face[0]

                if img_data is None:
                    logger.warning(
                        f'Face image data is empty for Face ID {face_id}')
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                        detail='Face image data is empty')

                img_bytes = bytes(img_data)
                logger.info(f'Retrieved face ID {face_id} successfully')
                return Response(content=img_bytes, media_type="image/jpeg")

    except Exception as ex:
        logger.error(f'Failed to retrieve face ID {face_id}: {ex}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to retrieve face'
        )


@app.get("/faces")
async def get_last_five_faces():
    try:
        with open_conn() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id FROM faces ORDER BY created_at DESC LIMIT 5")
                faces = cursor.fetchall()

                logger.info('Retrieved last five faces successfully')
                return [{'id': face[0]} for face in faces]
    except Exception as ex:
        logger.error(f'Failed to retrieve last five faces: {ex}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to retrieve faces'
        )


@app.post("/upload_face")
async def load_face(file: UploadFile = File(...)):
    face_id = str(uuid.uuid4())
    face_file = await file.read()
    logger.info(f'Received face upload with generated ID: {face_id}')

    try:
        with open_conn() as connection:
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO faces (id, img) VALUES (%s, %s)",
                               (face_id, psycopg2.Binary(face_file)))
                logger.info(
                    f'Face ID {face_id} successfully inserted into the database')
    except Exception as ex:
        logger.error(f'Failed to upload face ID {face_id}: {ex}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to upload face'
        )

    await notify_clients(face_id)
    return {'face_id': face_id}
