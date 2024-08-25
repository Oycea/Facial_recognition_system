import uuid

from fastapi import FastAPI, UploadFile, File, Response, HTTPException, status
from fastapi.websockets import WebSocket
from fastapi.templating import Jinja2Templates

app = FastAPI()

faces = []
clients = []
templates = Jinja2Templates(directory="templates")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except:
        clients.remove(websocket)


async def notify_clients(face_id: str):
    for client in clients:
        await client.send_text(face_id)


@app.get("/faces/{face_id}")
async def get_face(face_id: str):
    try:
        for face in faces:
            if face["id"] == face_id:
                return Response(content=face["face_file"], media_type="image/jpeg")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Face not found'
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Internal Server Error')


@app.get("/faces")
async def get_last_five_faces():
    return [{"id": face["id"]} for face in faces[-5:]]


@app.post("/upload_face")
async def load_face(file: UploadFile = File(...)):
    face_id = str(uuid.uuid4())
    face_info = {"id": face_id, "face_file": await file.read()}
    faces.append(face_info)

    await notify_clients(face_id)
    return {"face_id": face_id}
