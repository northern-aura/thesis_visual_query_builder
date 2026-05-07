import cv2 as cv
import base64
import sys
import time
import ujson
import argparse
import signal

from kafka import KafkaProducer

def signal_handler(signal, frame):
    print("Process terminated")
    cap.release()
    cv.destroyAllWindows()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# parser=argparse.ArgumentParser()
# parser.add_argument("--topic")
# parser.add_argument("--fps")
# args=parser.parse_args()
#
# topic = args.topic
# fps = int(args.fps)
topic = "input"
fps = 10

producer = KafkaProducer(bootstrap_servers=['127.0.0.1:9092'])
def send_message(key, value):
    producer.send(
        topic=topic, 
        key=str(key).encode(), 
        value=value
    )

annotations = []

cap = cv.VideoCapture(0)

if not cap.isOpened():
    print("Camera not detected");
    exit()

cap.set(cv.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv.CAP_PROP_FRAME_HEIGHT, 720)

frame_id = 0

while True: 
    ret, frame = cap.read()
    if not ret:
        print("Frame not correctly captured. Exiting.")
        break

    _, buffer = cv.imencode('.jpg', frame)
    image_encoded = base64.b64encode(buffer)
    send_message(
        frame_id,
        ujson.dumps({    
            "frame_id": frame_id,
            "frame" : image_encoded.decode(),
            "sent" : time.time(),
            "timestamp" : time.time_ns() // 1_000_000
        }).encode()
    )
    frame_id += 1
    cv.imshow('frame', frame)
    cv.waitKey(1)
    time.sleep(1/fps)

cap.release()
