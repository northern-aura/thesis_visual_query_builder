
import os
import cv2 as cv
import base64
import time
import ujson

from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic

print("Starting video sender...")
bootstrap_server = "localhost:9092"
topic_name = "cars_video"

# Topic clearing is opt-in via CLEAR_TOPIC=1. The UI clears the input topic BEFORE
# submitting the pipeline; if this script also clears it AFTER Flink subscribed,
# Flink stays bound to a stale topic UUID and silently sees 0 records.
if os.getenv("CLEAR_TOPIC", "").lower() in ("1", "true", "yes"):
    try:
        admin = KafkaAdminClient(bootstrap_servers=bootstrap_server)
        admin.delete_topics([topic_name])
        admin.close()
        print(f"Cleared old data from {topic_name} topic")
        time.sleep(3)  # Wait for Kafka to finish deletion
    except Exception as e:
        print(f"Note: Could not clear topic (may not exist yet): {e}")

producer = KafkaProducer(bootstrap_servers=[bootstrap_server])
csv_path = "cars-me/04/out_04.csv"

def send_message(key, value):
    producer.send(
        topic=topic_name,
        key=str(key).encode(),
        value=value
    )

annotations = []

with open(f"{csv_path}", "r") as af:
    for line in af.readlines():
        row = line.rstrip().split(",")
        # Pad short rows to [plate, brand, color] so indexing never fails
        while len(row) < 3:
            row.append("")
        annotations.append(row)

cap = cv.VideoCapture("cars-me/04/out_04.mp4")

frame_id = 0

while cap.isOpened():
    ret, frame = cap.read()

    if not ret:
        print("Can't receive frame (stream end?). Exiting ...")
        break

    if frame_id >= len(annotations):
        print(f"Annotations exhausted at frame {frame_id}. Stopping send.")
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
producer.flush()  # Ensure all messages are sent
producer.close()  # Clean shutdown
print("All frames sent successfully!")
