
import cv2 as cv
import base64
import time
import ujson
from kafka import KafkaProducer

print("Starting video sender...")
producer = KafkaProducer(bootstrap_servers=['127.0.0.1:9092'])
csv_path = "cars-me/04/out_04.csv"

annotations = []
with open(csv_path, "r") as af:
    for line in af.readlines():
        annotations.append(line.rstrip().split(","))

cap = cv.VideoCapture("cars-me/04/out_04.mp4")
frame_id = 0

while cap.isOpened() and frame_id < 60:
    ret, frame = cap.read()
    if not ret:
        print("Can't receive frame (stream end?). Exiting ...")
        break
    _, buffer = cv.imencode('.jpg', frame)
    image_encoded = base64.b64encode(buffer)
    annotation = annotations[frame_id]
    producer.send(
        topic="cars_video",
        key=str(frame_id).encode(),
        value=ujson.dumps({
            "frame": image_encoded.decode(),
            "plate": annotation[0],
            "brand": annotation[1],
            "color": annotation[2],
            "sent": time.time(),
            "timestamp": time.time_ns() // 1_000_000
        }).encode()
    )
    print(f"Sending frame {frame_id}, {annotation}")
    frame_id += 1
    time.sleep(1/20)

cap.release()
producer.flush()
producer.close()
print("All frames sent successfully!")
