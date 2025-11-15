
import cv2 as cv
import base64
import time
import ujson

from kafka import KafkaProducer

bootstrap_server = "localhost:9092"

producer = KafkaProducer(bootstrap_servers=['localhost:9092'])
video_path = "cars-me/04/out_04"

def send_message(key, value):
    producer.send(
        topic="cars_video", 
        key=str(key).encode(), 
        value=value
    )

annotations = []

with open(f"{video_path}.csv", "r") as af:
    for line in af.readlines():
        annotations.append(line.rstrip().split(","))

cap = cv.VideoCapture(f"{video_path}.mp4")

frame_id = 0

while cap.isOpened() and frame_id < 20:
    ret, frame = cap.read()

    if not ret:
        print("Can't receive frame (stream end?). Exiting ...")
        break

    _, buffer = cv.imencode('.jpg', frame)
    image_encoded = base64.b64encode(buffer)

    annotation = annotations[frame_id]

    send_message(
        frame_id,
        ujson.dumps({    
            "frame" : image_encoded.decode(),
            "plate" : annotation[0],
            "brand" : annotation[1],
            "color" : annotation[2],
            "sent" : time.time(),
            "timestamp" : time.time_ns() // 1_000_000
        }).encode()
    )
    
    print(f"Sending frame {frame_id}, {annotation}")

    frame_id += 1

    # Approx. 20 FPS
    time.sleep(1/20)

cap.release()
