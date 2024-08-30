import os
from io import BytesIO

import numpy as np
import cv2
import requests
import pika
from dotenv import load_dotenv

from face_detection import face_detector

load_dotenv()

RABBITMQ_HOST = os.getenv('RABBITMQ_HOST')
RABBITMQ_USER = os.getenv('RABBITMQ_USER')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS')
RABBITMQ_QUEUE = os.getenv('RABBITMQ_QUEUE')

FASTAPI_HOST = os.getenv('FASTAPI_HOST')
FASTAPI_PORT = os.getenv('FASTAPI_PORT')

required_vars = ['RABBITMQ_HOST', 'RABBITMQ_USER', 'RABBITMQ_PASS',
                 'RABBITMQ_QUEUE', 'FASTAPI_HOST', 'FASTAPI_PORT']
missing_vars = [var for var in required_vars if os.getenv(var) is None]

if missing_vars:
    raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")


FASTAPI_URL = f'http://{FASTAPI_HOST}:{FASTAPI_PORT}/upload_face'


def process_screen(ch, method, properties, body):
    screen = BytesIO(body)
    screen_list = np.frombuffer(screen.getvalue(), np.uint8)
    scr = cv2.imdecode(screen_list, cv2.IMREAD_COLOR)

    if scr is None:
        print('Failed to decode image')
        return

    faces = face_detector(scr)

    for i, face in enumerate(faces):
        _, buffer = cv2.imencode('.jpg', face)
        face_bytes = buffer.tobytes()
        response = requests.post(FASTAPI_URL, files={
            'file': ('face.jpg', face_bytes, 'image/jpeg')})
        print(f'Server response: {response.status_code}, {response.json()}')


connection_params = pika.ConnectionParameters(
    host=RABBITMQ_HOST,
    port=5672,
    credentials=pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS),
    virtual_host='/'
)

connection = pika.BlockingConnection(connection_params)
channel = connection.channel()

channel.queue_declare(queue=RABBITMQ_QUEUE, arguments={"x-max-priority": 10})

channel.basic_consume(queue=RABBITMQ_QUEUE, auto_ack=True,
                      on_message_callback=process_screen)

channel.start_consuming()
