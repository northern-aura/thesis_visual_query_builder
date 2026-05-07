
# Auto-generated node templates for Flink Python codegen
# Insert your logic in the placeholder sections

import glob
import logging
import time
import base64
import requests
import datetime
import os
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

from llm_call import prompt_llm, send_to_gpt, send_to_ollama, send_to_vllm, send_to_gpt_multi, send_to_ollama_multi, send_to_vllm_multi

FPS = 20
WINDOW_SIZE = 10
SKIP_AMOUNT = 0
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




class MapSkipFrames(MapFunction):
    def __init__(self, skip_on_empty, skip_on_detect):
        self.skip_on_empty = int(skip_on_empty)
        self.skip_on_detect = int(skip_on_detect)

    def map(self, data):
        op_start = time.time()
        # Pass both skip configs to downstream LLM via data dict
        data["_skip_on_empty"] = self.skip_on_empty
        data["_skip_on_detect"] = self.skip_on_detect
        op_end = time.time()
        data["latency_trace"] = data.get("latency_trace", []) + [
            {"operator": "SkipFrames", "start": op_start, "end": op_end,
             "duration_ms": round((op_end - op_start) * 1000, 2)}
        ]
        return data




class MapPromptLLM(MapFunction):
    def __init__(self, prompt, model="llava"):
        self.prompt = prompt
        self.model = model
        self._skip_countdown = -1
        self._skip_on_empty = 0
        self._skip_on_detect = 0

    def map(self, data):
        # Pick up skip config from upstream SkipFrames node (passed via data dict)
        if "_skip_on_empty" in data:
            self._skip_on_empty = data.pop("_skip_on_empty")
        if "_skip_on_detect" in data:
            self._skip_on_detect = data.pop("_skip_on_detect")

        # Short-circuit: if already marked as SKIP by upstream filter (CV Color Filter etc.), pass through
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

        # Adaptive skip: if countdown active, skip this frame (no API call)
        if self._skip_countdown > 0:
            self._skip_countdown -= 1
            op_start = time.time()
            op_end = time.time()
            return {
                "result": "SKIP",
                "annotation_plate": data.get("annotation_plate", ""),
                "annotation_brand": data.get("annotation_brand", ""),
                "annotation_color": data.get("annotation_color", ""),
                "sent": data["sent"],
                "in": data["in"],
                "llm_time": 0,
                "llm": "",
                "latency_trace": data.get("latency_trace", []) + [{"operator": "LLM", "start": op_start, "end": op_end, "duration_ms": 0.0}]
            }

        op_start = time.time()

        # Detect single-image vs multi-image (from Frame Batcher)
        if "images" in data:
            images = data["images"]
        else:
            images = [data["image"]]

        # Use the selected model for LLM calls
        if len(images) > 1:
            # Multi-image batch call
            if self.model == "gpt-4o":
                answer, llm = send_to_gpt_multi(images, self.prompt)
            elif self.model == "qwen2.5-vl-3b":
                answer, llm = send_to_vllm_multi("RedHatAI/Qwen2.5-VL-7B-Instruct-quantized.w8a8", images, self.prompt)
            else:
                answer, llm = send_to_ollama_multi(self.model, images, self.prompt)
        else:
            # Single-image call (original path)
            if self.model == "gpt-4o":
                answer, llm = send_to_gpt(images[0], self.prompt)
            elif self.model == "qwen2.5-vl-3b":
                answer, llm = send_to_vllm("RedHatAI/Qwen2.5-VL-7B-Instruct-quantized.w8a8", images[0], self.prompt)
            else:
                answer, llm = send_to_ollama(self.model, images[0], self.prompt)

        op_end = time.time()

        # Adaptive skip: set countdown based on whether frame was empty or had a detection
        if answer.upper().strip() == "SKIP" and self._skip_on_empty > 0:
            self._skip_countdown = self._skip_on_empty
        elif answer.upper().strip() != "SKIP" and self._skip_on_detect > 0:
            self._skip_countdown = self._skip_on_detect

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
    def __init__(self, topic):
        self.topic = topic
        self._results = []
        self._start_time = None

    def map(self, data):
        now = time.time()
        if self._start_time is None:
            self._start_time = now

        # If this is windowed data (already has metrics from MapGetCounts), pass through
        if "metrics" in data and data["metrics"]:
            self._results.append(data)
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
        # Only exclude frames that were never sent to LLM (llm_time == 0 and result SKIP)
        # LLM returning SKIP (llm_time > 0) is a real decision and counts
        result_val = data.get("result", "").strip()
        accuracy = {}
        was_node_skipped = result_val.upper() == "SKIP" and data.get("llm_time", 0) == 0
        if not was_node_skipped:
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

        self._results.append(data)
        return data

    def close(self):
        if not self._results:
            return

        total = len(self._results)
        runtime_s = round(time.time() - self._start_time, 2) if self._start_time else 0

        # Check if windowed (results have "frames" key) or per-frame
        is_windowed = "frames" in self._results[0]

        if is_windowed:
            # Windowed: aggregate across windows
            total_frames = sum(r.get("frames", 0) for r in self._results)
            acc_sums = {}
            acc_counts = {}
            for r in self._results:
                for k, v in r.get("metrics", {}).get("accuracy", {}).items():
                    acc_sums[k] = acc_sums.get(k, 0) + v
                    acc_counts[k] = acc_counts.get(k, 0) + 1
            accuracy = {k: round(acc_sums[k] / acc_counts[k], 4) for k in acc_sums}

            summary = {
                "topic": self.topic,
                "windows": total,
                "total_frames": total_frames,
                "pipeline_runtime_s": runtime_s,
                "accuracy": accuracy
            }
        else:
            # Per-frame: aggregate across individual frames
            # Node-skipped = SKIP result with llm_time 0 (never sent to LLM)
            node_skipped = sum(1 for r in self._results if r.get("result", "").upper().strip() == "SKIP" and r.get("metrics", {}).get("llm_time_ms", 0) == 0)
            processed = total - node_skipped

            llm_times = [r.get("metrics", {}).get("llm_time_ms", 0) for r in self._results if not (r.get("result", "").upper().strip() == "SKIP" and r.get("metrics", {}).get("llm_time_ms", 0) == 0)]
            e2e_times = [r.get("metrics", {}).get("e2e_latency_ms", 0) for r in self._results]

            acc_sums = {}
            acc_counts = {}
            for r in self._results:
                for k, v in r.get("metrics", {}).get("accuracy", {}).items():
                    if isinstance(v, bool):
                        acc_sums[k] = acc_sums.get(k, 0) + (1 if v else 0)
                    else:
                        acc_sums[k] = acc_sums.get(k, 0) + v
                    acc_counts[k] = acc_counts.get(k, 0) + 1
            accuracy = {k: round(acc_sums[k] / acc_counts[k], 4) for k in acc_sums}

            summary = {
                "topic": self.topic,
                "total_frames": total,
                "processed_frames": processed,
                "node_skipped_frames": node_skipped,
                "pipeline_runtime_s": runtime_s,
                "avg_llm_time_ms": round(sum(llm_times) / len(llm_times), 2) if llm_times else 0,
                "avg_e2e_latency_ms": round(sum(e2e_times) / len(e2e_times), 2) if e2e_times else 0,
                "accuracy": accuracy
            }

        os.makedirs("results", exist_ok=True)
        path = f"results/{self.topic}_summary.json"
        with open(path, "w") as f:
            ujson.dump(summary, f, indent=2)
        print(f"Final metrics written to {path}")




env = StreamExecutionEnvironment.get_execution_environment()

kafka_source = KafkaSource.builder()\
  .set_bootstrap_servers("kafka:9093")\
  .set_group_id("dashboard_1776778220507_0")\
  .set_topics("cars_video")\
  .set_starting_offsets(KafkaOffsetsInitializer.earliest())\
  .set_value_only_deserializer(SimpleStringSchema())\
  .build()

watermark_strategy = WatermarkStrategy.for_bounded_out_of_orderness(Duration.of_seconds(0))\
  .with_timestamp_assigner(lambda e,_: ujson.loads(e)["timestamp"])

stream = env.from_source(kafka_source, watermark_strategy, "Kafka Source")

# Procesing Node 1 (decode)
stream_1 = stream.map(MapDecodeStream())
# Procesing Node 2 (skip frames)
stream_2 = stream_1.map(MapSkipFrames(10, 0))
# Procesing Node 3 (llm)
stream_3 = stream_2.map(MapPromptLLM("""Is there a car visible in this image? If yes, is the car red (do not take into consideration the bumper)? If the car is red, return its license plate in uppercase without any whitespaces. If the car is not red or there is no car or no license plate is visible, return the string SKIP.

Do not provide any text or any explanation, just the final answer in the correct format!""", """qwen2.5-vl-3b"""))

# Compute metrics (accuracy, latency) before sending to sink
stream_metrics = stream_3.map(MapComputeMetrics("cars_color_plate_skip10"))

kafka_sink = KafkaSink.builder()\
  .set_bootstrap_servers("kafka:9093")\
  .set_record_serializer(KafkaRecordSerializationSchema.builder()\
       .set_topic("cars_color_plate_skip10")\
       .set_value_serialization_schema(SimpleStringSchema())\
       .build())\
  .build()

stream_metrics.map(lambda x: ujson.dumps(x)).map(lambda x: x, Types.STRING()).sink_to(kafka_sink)

env.execute("Color + Plate (Skip 10)")
