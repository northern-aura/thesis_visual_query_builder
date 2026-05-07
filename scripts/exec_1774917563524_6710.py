
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




class MapResizeImage(MapFunction):
    def __init__(self, width_lbound, width_rbound, height_lbound, height_rbound):
        self.width_lbound = width_lbound
        self.width_rbound = width_rbound
        self.height_lbound = height_lbound
        self.height_rbound = height_rbound

    def map(self, data):
        # Short-circuit: if already marked as SKIP by upstream filter, pass through
        if "result" in data and data.get("result") == "SKIP":
            return data

        op_start = time.time()
        image = data["image"]

        # Select random dimensions within the specified ranges
        width = random.randint(self.width_lbound, self.width_rbound)
        height = random.randint(self.height_lbound, self.height_rbound)

        resized = cv.resize(image, (width, height), interpolation=cv.INTER_AREA)
        op_end = time.time()

        return {
            "image" : resized,
            "annotation_plate": data.get("annotation_plate", ""),
            "annotation_brand": data.get("annotation_brand", ""),
            "annotation_color": data.get("annotation_color", ""),
            "sent" : data["sent"],
            "in" : data["in"],
            "latency_trace": data.get("latency_trace", []) + [{"operator": "Resize", "start": op_start, "end": op_end, "duration_ms": round((op_end - op_start) * 1000, 2)}]
        }




class MapCVColorFilter(MapFunction):
    # HSV ranges for each color preset
    COLOR_RANGES = {
        "cv_color_red":    [( 0,  70,  50,  10, 255, 255), (170,  70,  50, 180, 255, 255)],
        "cv_color_blue":   [(100,  70,  50, 130, 255, 255)],
        "cv_color_white":  [(  0,   0, 200, 180,  30, 255)],
        "cv_color_grey":   [(  0,   0,  80, 180,  40, 200)],
        "cv_color_black":  [(  0,   0,   0, 180, 255,  50)],
        "cv_color_green":  [( 35,  70,  50,  85, 255, 255)],
        "cv_color_yellow": [( 20,  70,  50,  35, 255, 255)],
    }

    def __init__(self, color_key, threshold=5):
        self.color_key = color_key
        self.threshold = float(threshold) / 100.0  # convert percentage to ratio
        self.ranges = self.COLOR_RANGES.get(color_key, [])

    def map(self, data):
        op_start = time.time()
        image = data["image"]
        hsv = cv.cvtColor(image, cv.COLOR_BGR2HSV)

        combined_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for (h_lo, s_lo, v_lo, h_hi, s_hi, v_hi) in self.ranges:
            lower = np.array([h_lo, s_lo, v_lo])
            upper = np.array([h_hi, s_hi, v_hi])
            mask = cv.inRange(hsv, lower, upper)
            combined_mask = cv.bitwise_or(combined_mask, mask)

        ratio = cv.countNonZero(combined_mask) / (combined_mask.shape[0] * combined_mask.shape[1])
        op_end = time.time()

        trace_entry = {"operator": "CVColorFilter", "start": op_start, "end": op_end, "duration_ms": round((op_end - op_start) * 1000, 2)}
        new_trace = data.get("latency_trace", []) + [trace_entry]

        if ratio >= self.threshold:
            return {
                "image": image,
                "annotation_plate": data.get("annotation_plate", ""),
                "annotation_brand": data.get("annotation_brand", ""),
                "annotation_color": data.get("annotation_color", ""),
                "sent": data["sent"],
                "in": data["in"],
                "latency_trace": new_trace
            }
        else:
            return {
                "result": "SKIP",
                "annotation_plate": data.get("annotation_plate", ""),
                "annotation_brand": data.get("annotation_brand", ""),
                "annotation_color": data.get("annotation_color", ""),
                "sent": data["sent"],
                "in": data["in"],
                "latency_trace": new_trace
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




class FilterNotEmpty(FilterFunction):
    def filter(self, data):
        return data["result"] != ""




class FilterNotSkipped(FilterFunction):
    def filter(self, data):
        val = data["result"].strip().upper()
        return val != "SKIP" and val != "SKIPPED"




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
  .set_starting_offsets(KafkaOffsetsInitializer.latest())  .set_value_only_deserializer(SimpleStringSchema())\
  .build()

watermark_strategy = WatermarkStrategy.for_bounded_out_of_orderness(Duration.of_seconds(0))\
  .with_timestamp_assigner(lambda e,_: ujson.loads(e)["timestamp"])

stream = env.from_source(kafka_source, watermark_strategy, "Kafka Source")

# Procesing Node 1 (decode)
stream_1 = stream.map(MapDecodeStream())
# Procesing Node 2 (resize)
stream_2 = stream_1.map(MapResizeImage(320,640,180,360))
# Procesing Node 3 (cv color filter)
stream_3 = stream_2.map(MapCVColorFilter("cv_color_red", 10))
# Procesing Node 4 (llm)
stream_4 = stream_3.map(MapPromptLLM("""Is there a car visible in this image? If yes, is the car red (do not take into consideration the bumper)? If the car is red, return "red". If the car is not red or there is no car, return the string SKIP.

Do not provide any text or any explanation, just the final answer in the correct format!""", """gpt-4o"""))
# Procesing Node 5 (filter)
stream_5 = stream_4.filter(FilterNotEmpty())
# Procesing Node 6 (filter)
stream_6 = stream_5.filter(FilterNotSkipped())

# Compute metrics (accuracy, latency) before sending to sink
stream_metrics = stream_6.map(MapComputeMetrics())

kafka_sink = KafkaSink.builder()\
  .set_bootstrap_servers("kafka:9093")\
  .set_record_serializer(KafkaRecordSerializationSchema.builder()\
       .set_topic("cars_color_red")\
       .set_value_serialization_schema(SimpleStringSchema())\
       .build())\
  .build()

stream_metrics.map(lambda x: ujson.dumps(x)).map(lambda x: x, Types.STRING()).sink_to(kafka_sink)

env.execute("Car Color Red")
