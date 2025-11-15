import glob
import logging
import time
import base64
import requests
import random
import datetime
import ujson

import numpy as np
import cv2 as cv

from pyflink.common import Encoder, Types, Time, WatermarkStrategy, Duration
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.watermark_strategy import TimestampAssigner

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.file_system import FileSource, StreamFormat, FileSink, OutputFileConfig, RollingPolicy
from pyflink.datastream.connectors.kafka import FlinkKafkaConsumer, KafkaSink, KafkaRecordSerializationSchema, KafkaSource
from pyflink.datastream.functions import MapFunction, ReduceFunction, ProcessWindowFunction, ProcessAllWindowFunction, FilterFunction, ProcessFunction
from pyflink.datastream.window import TumblingEventTimeWindows, TumblingProcessingTimeWindows

from llm_call import prompt_llm

from pyflink.common import Types


FPS = 20
WINDOW_SIZE = 10
SKIP_AMOUNT = 10
SKIP_COUNTDOWN = -1

### MAP FUNCTIONS #########

class MapDecodeStream(MapFunction):
    
    def map(self, encoded_data):

        decoded_data = ujson.loads(encoded_data)
        
        # Decode the image  
        decoded_image = base64.b64decode(decoded_data["frame"])
        np_data = np.fromstring(decoded_image,np.uint8)
        image = cv.imdecode(np_data, cv.IMREAD_UNCHANGED)

        return {
            "image" : image,
            "annotation" : decoded_data["plate"],
            "sent" : decoded_data["sent"],
            "in" : time.time()
        }

class MapPromptLLM(MapFunction):

    def map(self, data):

        global SKIP_AMOUNT
        global SKIP_COUNTDOWN

        prompt = """
            Is there a license plate visible in this image? If yes, return the text of the license plate in uppercase without any whitespaces. If there is no license plate in the image, return the string SKIP.

            Do not provide any text or any explanation, just the final answer in the correct format!
        """
        start = time.time()

        if SKIP_COUNTDOWN > 0:
            answer = "SKIPPED"
            llm = "SKIPPED"
            SKIP_COUNTDOWN -= 1
        
        else:
            answer, llm = prompt_llm(data["image"],prompt)

            if answer.strip() == "" or answer.strip() == "\"\"" or answer.strip().upper() == "SKIP":
                answer = ""
                SKIP_COUNTDOWN = SKIP_AMOUNT

        end = time.time()

        if answer == "\"\"":
            answer = ""

        return {
            "result" : answer.upper().strip(),
            "annotation" : data["annotation"].upper(),
            "sent" : data["sent"],
            "in" : data["in"],
            "llm_time" : end-start,
            "llm" : llm
        }

class MapRecolorImage(MapFunction):
    
    def map(self, data):
        image = data["image"]

        return {
            "image" : cv.cvtColor(image, cv.COLOR_BGR2GRAY),
            "annotation" : data["annotation"],
            "sent" : data["sent"],
            "in" : data["in"]
        }
    
class MapResizeImage(MapFunction):
    def map(self, data):
        image = data["image"]

        return {
            "image" : cv.resize(image, (640, 360), interpolation=cv.INTER_AREA),
            "annotation" : data["annotation"],
            "sent" : data["sent"],
            "in" : data["in"]
        }

class MapAddMetrics(MapFunction):
    def map(self, data):
        #latency = time.time() - data[2]
        def get_accuracy(predicted_plate, ground_truth_plate):
            length = max(len(predicted_plate), len(ground_truth_plate))

            if length == 0:
                return 1.0
            
            matches = sum(1 for p, g in zip(predicted_plate, ground_truth_plate) if p == g)

            return matches/length
        
        return {
            "Query": "License Plate Recognition Optimised + Skipping",
            "LLM": data["llm"],
            
            "Result": data["result"],
            "Ground Truth": data["annotation"],

            "Sent" : data["sent"],
            "In": datetime.datetime.fromtimestamp(data["in"]).strftime('%H:%M:%S'),
            "Out": datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S'),

            "Frame Latency" : time.time() - data["in"],
            "LLM Latency": data["llm_time"],

            "Accuracy": get_accuracy(data["result"], data["annotation"])
        }
    
###########################

env = StreamExecutionEnvironment.get_execution_environment()

kafka_source = KafkaSource.builder()\
    .set_bootstrap_servers("kafka:9093")\
    .set_group_id("cars")\
    .set_topics("cars_video")\
    .set_value_only_deserializer(SimpleStringSchema())\
    .build()

watermark_strategy = WatermarkStrategy.for_monotonous_timestamps().with_timestamp_assigner(lambda event, _ : ujson.loads(event)["timestamp"])

video_stream = env.from_source(kafka_source, watermark_strategy, "Kafka Source")

# DECODE STREAM ###
decoded_video_stream = video_stream.map(MapDecodeStream())

# APPLY CV PIPELINE
recolored_video_stream = decoded_video_stream.map(MapRecolorImage())
resized_video_stream = recolored_video_stream.map(MapResizeImage())

# SEND FRAME TO LLM ###
llm_answer_stream = resized_video_stream.map(MapPromptLLM())


result_stream = llm_answer_stream.map(MapAddMetrics())

kafka_sink = KafkaSink.builder() \
                      .set_bootstrap_servers("kafka:9093") \
                      .set_record_serializer(KafkaRecordSerializationSchema.builder()
                                                                           .set_topic("cars_query_license_plate_recognition_optimised_skipping")
                                                                           .set_value_serialization_schema(SimpleStringSchema())
                                                                           .build()) \
                      .build()

result_stream.map(lambda x : ujson.dumps(x)).map(lambda x: x, Types.STRING()).sink_to(kafka_sink)

env.execute("Query: License Plate Recognition (Optimised + Skipping) - Job")
