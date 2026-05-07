
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




class ReduceWindowResults(ReduceFunction):
    def reduce(self, value1, value2):
        return {
            "result" : [*value1["result"], *value2["result"]],
            "annotation_plates": [*value1.get("annotation_plates", []), *value2.get("annotation_plates", [])],
            "annotation_brands": [*value1.get("annotation_brands", []), *value2.get("annotation_brands", [])],
            "annotation_colors": [*value1.get("annotation_colors", []), *value2.get("annotation_colors", [])],
            "sent_first" : min(value1["sent_first"], value2["sent_first"]),
            "sent_last" : max(value1["sent_last"], value2["sent_last"]),
            "in_first" : min(value1["in_first"], value2["in_first"]),
            "in_last" : max(value1["in_last"], value2["in_last"]),
            "llm_time" : [*value1["llm_time"], *value2["llm_time"]],
            "llm" : value1["llm"],
            "latency_traces": [*value1.get("latency_traces", []), *value2.get("latency_traces", [])]
        }




class MapChangeFormat(MapFunction):
    def map(self, data):
        return {
            "result" : [data["result"]],
            "annotation_plates": [data.get("annotation_plate", "")],
            "annotation_brands": [data.get("annotation_brand", "")],
            "annotation_colors": [data.get("annotation_color", "")],
            "sent_first" : data["sent"],
            "sent_last" : data["sent"],
            "in_first" : data["in"],
            "in_last" : data["in"],
            "llm_time" : [data.get("llm_time", 0)],
            "llm" : data.get("llm", ""),
            "latency_traces": [data.get("latency_trace", [])]
        }





class MapGetCounts(MapFunction):
    def map(self, data):

        result_v, result_c = np.unique(data["result"], return_counts=True)

        # Per-frame accuracy computation
        results = data["result"]
        ann_brands = data.get("annotation_brands", [])
        ann_colors = data.get("annotation_colors", [])
        ann_plates = data.get("annotation_plates", [])
        frames = len(results)

        brand_matches = sum(1 for i in range(min(frames, len(ann_brands))) if results[i].lower().strip() == ann_brands[i].lower().strip()) if ann_brands and ann_brands[0] else None
        color_matches = sum(1 for i in range(min(frames, len(ann_colors))) if results[i].lower().strip() == ann_colors[i].lower().strip()) if ann_colors and ann_colors[0] else None
        plate_matches = sum(1 for i in range(min(frames, len(ann_plates))) if results[i].upper().strip() == ann_plates[i].upper().strip()) if ann_plates and ann_plates[0] else None

        accuracy = {}
        if brand_matches is not None:
            accuracy["brand_accuracy"] = round(brand_matches / frames, 4) if frames > 0 else 0
        if color_matches is not None:
            accuracy["color_accuracy"] = round(color_matches / frames, 4) if frames > 0 else 0
        if plate_matches is not None:
            accuracy["plate_accuracy"] = round(plate_matches / frames, 4) if frames > 0 else 0

        # Aggregate latency metrics from all frames
        traces = data.get("latency_traces", [])
        avg_operator_latencies = {}
        avg_between_nodes = {}
        if traces:
            op_totals = {}
            op_counts = {}
            gap_totals = {}
            gap_counts = {}
            for trace in traces:
                for t in trace:
                    op = t["operator"]
                    op_totals[op] = op_totals.get(op, 0) + t["duration_ms"]
                    op_counts[op] = op_counts.get(op, 0) + 1
                for i in range(len(trace) - 1):
                    key = trace[i]["operator"] + " -> " + trace[i+1]["operator"]
                    gap_ms = round((trace[i+1]["start"] - trace[i]["end"]) * 1000, 2)
                    gap_totals[key] = gap_totals.get(key, 0) + gap_ms
                    gap_counts[key] = gap_counts.get(key, 0) + 1
            avg_operator_latencies = {op: round(op_totals[op] / op_counts[op], 2) for op in op_totals}
            avg_between_nodes = {key: round(gap_totals[key] / gap_counts[key], 2) for key in gap_totals}

        return {
            "result" : [(v,int(c)) for v,c in zip(result_v, result_c)],
            "sent_first" : data["sent_first"],
            "sent_last" : data["sent_last"],
            "in_first" : data["in_first"],
            "in_last" : data["in_last"],
            "llm_time" : data["llm_time"],
            "llm" : data["llm"],
            "frames" : frames,
            "metrics": {
                "accuracy": accuracy,
                "avg_operator_latencies_ms": avg_operator_latencies,
                "avg_between_nodes_ms": avg_between_nodes,
                "avg_llm_time_ms": round(sum(data["llm_time"]) / len(data["llm_time"]) * 1000, 2) if data["llm_time"] else 0,
                "window_e2e_ms": round((data["in_last"] - data["sent_first"]) * 1000, 2)
            }
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
stream_2 = stream_1.map(MapPromptLLM("""Is there a car visible in this image? If yes, return the brand of the car. The answer should be in lowercase and ignore any umlaut (e.g. citroen). In case that there are two cars in the frame, return the brand of the one which has a visible license plate. If there is no car in the image or you cannot identify the brand, return the string SKIP.

Do not provide any text or any explanation, just the final answer in the correct format!""", """gpt-4o"""))
# Procesing Node 3 (window)
stream_3 = stream_2.map(MapChangeFormat()).window_all(TumblingProcessingTimeWindows.of(Time.seconds(10))).reduce(ReduceWindowResults())
# Procesing Node 4 (aggr)
stream_4 = stream_3.map(MapGetCounts())

# Compute metrics (accuracy, latency) before sending to sink
stream_metrics = stream_4.map(MapComputeMetrics())

kafka_sink = KafkaSink.builder()\
  .set_bootstrap_servers("kafka:9093")\
  .set_record_serializer(KafkaRecordSerializationSchema.builder()\
       .set_topic("cars_most_popular_brand")\
       .set_value_serialization_schema(SimpleStringSchema())\
       .build())\
  .build()

stream_metrics.map(lambda x: ujson.dumps(x)).map(lambda x: x, Types.STRING()).sink_to(kafka_sink)

env.execute("Most Popular Brand")
