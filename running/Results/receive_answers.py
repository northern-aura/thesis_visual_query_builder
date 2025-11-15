from kafka import KafkaConsumer
import ujson

import time
from datetime import datetime


# Define Kafka consumer
consumer = KafkaConsumer(
    "cars_query_license_plate_recognition_optimised_skipping",
    bootstrap_servers="localhost:9092",  # Kafka broker address
    auto_offset_reset="earliest",  # Start reading from the beginning
    #group_id="cars",  # Consumer group ID
    enable_auto_commit=True  # Auto commit offsets 
)

file_name = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

print(f"Started listener | Output file: {file_name}.txt")


out = open(f"{file_name}.txt", "w")

# Consume messages
for message in consumer:
    #print(message.topic, message.value.decode('utf-8'))

    received = time.time()

    print(f"{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')} - Received: {message.topic}")

    msg = ujson.loads(message.value.decode('utf-8'))

    msg["Received"] = datetime.fromtimestamp(received).strftime('%H:%M:%S')

    if "Sent" in msg:
        msg["System Latency"] = received - msg["Sent"]
        msg["Sent"] = datetime.fromtimestamp(msg["Sent"]).strftime('%H:%M:%S')
    
    else:
        msg["System Latency First"] = received - msg["Sent First"]
        msg["System Latency Last"] = received - msg["Sent Last"]

        msg["Sent First"] = datetime.fromtimestamp(msg["Sent First"]).strftime('%H:%M:%S')
        msg["Sent Last"] = datetime.fromtimestamp(msg["Sent Last"]).strftime('%H:%M:%S')


    #out.write(message.topic)
    out.write(ujson.dumps(msg) + "\n")
    out.flush()