#!/usr/bin/env python3
import sys
import os

print("=== Testing Kafka Video Sender ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")

# Test 1: Check if files exist
print("\n1. Checking files:")
csv_file = "cars-me/04/out_04.csv"
video_file = "cars-me/04/out_04.mp4"

if os.path.exists(csv_file):
    print(f"✓ CSV found: {csv_file}")
else:
    print(f"✗ CSV NOT found: {csv_file}")

if os.path.exists(video_file):
    print(f"✓ Video found: {video_file}")
else:
    print(f"✗ Video NOT found: {video_file}")

# Test 2: Try importing required libraries
print("\n2. Checking Python libraries:")
try:
    import cv2
    print("✓ OpenCV (cv2) installed")
except ImportError as e:
    print(f"✗ OpenCV NOT installed: {e}")

try:
    import ujson
    print("✓ ujson installed")
except ImportError as e:
    print(f"✗ ujson NOT installed: {e}")

try:
    from kafka import KafkaProducer
    print("✓ kafka-python installed")
except ImportError as e:
    print(f"✗ kafka-python NOT installed: {e}")

# Test 3: Try connecting to Kafka
print("\n3. Testing Kafka connection:")
try:
    from kafka import KafkaProducer
    producer = KafkaProducer(bootstrap_servers=['localhost:9092'])
    print("✓ Connected to Kafka at localhost:9092")
    producer.close()
except Exception as e:
    print(f"✗ Cannot connect to Kafka: {e}")
    print("  Make sure Docker containers are running!")

print("\n=== Test Complete ===")
