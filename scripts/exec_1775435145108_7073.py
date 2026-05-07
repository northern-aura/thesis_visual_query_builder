
# Auto-generated node templates for Flink Python codegen
# Insert your logic in the placeholder sections

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
from pyflink.datastream.connectors.kafka import FlinkKafkaConsumer, KafkaSink, KafkaRecordSerializationSchema, KafkaSource, KafkaOffsetsInitializer
from pyflink.datastream.functions import MapFunction, ReduceFunction, ProcessWindowFunction, ProcessAllWindowFunction, FilterFunction, ProcessFunction
from pyflink.datastream.window import TumblingEventTimeWindows, TumblingProcessingTimeWindows

from llm_call import prompt_llm, send_to_gpt, send_to_ollama

FPS = 20
WINDOW_SIZE = 10
SKIP_AMOUNT = 10
SKIP_COUNTDOWN = -1

### MAP FUNCTIONS #########



class MapDecodeStream(MapFunction):

    def map(self, encoded_data):
        op_start = time.time()

        decoded_data = ujson.loads(encoded_data)

        # Decode the image
        decoded_image = base64.b64decode(decoded_data["frame"])
        np_data = np.fromstring(decoded_image,np.uint8)
        image = cv.imdecode(np_data, cv.IMREAD_UNCHANGED)

        op_end = time.time()

        return {
            "image" : image,
            "annotation_plate": decoded_data.get("plate", ""),
            "annotation_brand": decoded_data.get("brand", ""),
            "annotation_color": decoded_data.get("color", ""),
            "sent" : decoded_data["sent"],
            "in" : op_start,
            "latency_trace": [{"operator": "Decode", "start": op_start, "end": op_end, "duration_ms": round((op_end - op_start) * 1000, 2)}]
        }




class MapPromptLLM(MapFunction):
    def __init__(self, prompt, model="llava"):
        self.prompt = prompt
        self.model = model

    def map(self, data):
        # Short-circuit: if already marked as SKIP by upstream filter, pass through
        if "result" in data and data.get("result") == "SKIP":
            return {
                "result": "SKIP",
                "annotation_plate": data.get("annotation_plate", ""),
                "annotation_brand": data.get("annotation_brand", ""),
                "annotation_color": data.get("annotation_color", ""),
                "sent": data["sent"],
                "in": data["in"],
                "llm_time": 0,
                "llm": "",
                "latency_trace": data.get("latency_trace", [])
            }

        global SKIP_AMOUNT
        global SKIP_COUNTDOWN

        op_start = time.time()

        # Use the selected model for LLM calls
        if self.model == "gpt-4o":
            answer, llm = send_to_gpt(data["image"], self.prompt)
        else:
            # Use Ollama for all other models
            answer, llm = send_to_ollama(self.model, data["image"], self.prompt)

        op_end = time.time()

        return {
            "result" : answer.upper().strip(),
            "annotation_plate": data.get("annotation_plate", ""),
            "annotation_brand": data.get("annotation_brand", ""),
            "annotation_color": data.get("annotation_color", ""),
            "sent" : data["sent"],
            "in" : data["in"],
            "llm_time" : op_end - op_start,
            "llm" : llm,
            "latency_trace": data.get("latency_trace", []) + [{"operator": "LLM", "start": op_start, "end": op_end, "duration_ms": round((op_end - op_start) * 1000, 2)}]
        }




class MapComputeMetrics(MapFunction):
    def map(self, data):
        now = time.time()

        # If this is windowed data (already has metrics from MapGetCounts), pass through
        if "metrics" in data and data["metrics"]:
            return data

        trace = data.get("latency_trace", [])

        # Per-operator latency
        operator_latencies = {}
        for t in trace:
            operator_latencies[t["operator"]] = t["duration_ms"]

        # Between-nodes latency (Flink scheduling overhead)
        between_nodes = []
        for i in range(len(trace) - 1):
            gap_ms = round((trace[i+1]["start"] - trace[i]["end"]) * 1000, 2)
            between_nodes.append({
                "from": trace[i]["operator"],
                "to": trace[i+1]["operator"],
                "gap_ms": gap_ms
            })

        # End-to-end latency
        e2e_ms = round((now - data.get("sent", now)) * 1000, 2)

        # Accuracy (compare result to ground truth)
        result_val = data.get("result", "").strip()
        accuracy = {}
        ann_brand = data.get("annotation_brand", "")
        ann_color = data.get("annotation_color", "")
        ann_plate = data.get("annotation_plate", "")
        if ann_brand:
            accuracy["brand_match"] = result_val.lower() == ann_brand.lower().strip()
        if ann_color:
            accuracy["color_match"] = result_val.lower() == ann_color.lower().strip()
        if ann_plate:
            accuracy["plate_match"] = result_val.upper() == ann_plate.upper().strip()

        data["metrics"] = {
            "e2e_latency_ms": e2e_ms,
            "operator_latencies_ms": operator_latencies,
            "between_nodes_ms": between_nodes,
            "accuracy": accuracy,
            "llm_time_ms": round(data.get("llm_time", 0) * 1000, 2)
        }

        # Clean up large fields before sending to sink
        data.pop("latency_trace", None)
        data.pop("image", None)

        return data




env = StreamExecutionEnvironment.get_execution_environment()

kafka_source = KafkaSource.builder()\
  .set_bootstrap_servers("kafka:9093")\
  .set_group_id("cars")\
  .set_topics("cars_video")\
  .set_starting_offsets(KafkaOffsetsInitializer.earliest())  .set_value_only_deserializer(SimpleStringSchema())\
  .build()

watermark_strategy = WatermarkStrategy.for_bounded_out_of_orderness(Duration.of_seconds(0))\
  .with_timestamp_assigner(lambda e,_: ujson.loads(e)["timestamp"])

stream = env.from_source(kafka_source, watermark_strategy, "Kafka Source")

# Procesing Node 1 (decode)
stream_1 = stream.map(MapDecodeStream())
# Procesing Node 2 (llm)
stream_2 = stream_1.map(MapPromptLLM("""Is there a license plate visible in this image? If yes, read the license plate text. If the license plate reads "QRF213" (ignoring whitespace), return "QRF213". Otherwise, return the string SKIP.

Do not provide any text or any explanation, just the final answer in the correct format!""", """gpt-4o"""))

# Compute metrics (accuracy, latency) before sending to sink
stream_metrics = stream_2.map(MapComputeMetrics())

kafka_sink = KafkaSink.builder()\
  .set_bootstrap_servers("kafka:9093")\
  .set_record_serializer(KafkaRecordSerializationSchema.builder()\
       .set_topic("cars_specific_plate_qrf213")\
       .set_value_serialization_schema(SimpleStringSchema())\
       .build())\
  .build()

stream_metrics.map(lambda x: ujson.dumps(x)).map(lambda x: x, Types.STRING()).sink_to(kafka_sink)

env.execute("Specific Plate: QRF213")
