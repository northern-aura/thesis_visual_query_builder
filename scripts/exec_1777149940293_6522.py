
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
            "annotation_action": decoded_data.get("gt_action", ""),
            "sent" : decoded_data["sent"],
            "in" : op_start,
            "latency_trace": [{"operator": "Decode", "start": op_start, "end": op_end, "duration_ms": round((op_end - op_start) * 1000, 2)}]
        }




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
                "annotation_action": data.get("annotation_action", ""),
                "annotation_actions": data.get("annotation_actions", []),
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
                "annotation_action": data.get("annotation_action", ""),
                "annotation_actions": data.get("annotation_actions", []),
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
            "annotation_action": data.get("annotation_action", ""),
            "annotation_actions": data.get("annotation_actions", []),
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
            "annotation_actions": [*value1.get("annotation_actions", []), *value2.get("annotation_actions", [])],
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
        ann_action = data.get("annotation_action", "")
        if not ann_action:
            ann_actions = data.get("annotation_actions", [])
            if isinstance(ann_actions, list) and len(ann_actions) > 0:
                ann_action = ann_actions[0]
        return {
            "result" : [data["result"]],
            "annotation_plates": [data.get("annotation_plate", "")],
            "annotation_brands": [data.get("annotation_brand", "")],
            "annotation_colors": [data.get("annotation_color", "")],
            "annotation_actions": [ann_action],
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
        incoming_metrics = data.get("metrics", {})
        if not isinstance(incoming_metrics, dict):
            incoming_metrics = {}
        # Preserve frame count when this runs as a second aggregation pass
        # (e.g. remove_count_less_than -> aggr). In that path, result may be
        # filtered down to [] even though many frames were processed.
        incoming_frames = data.get("frames", None)
        if isinstance(incoming_frames, (int, float)):
            frame_count = max(0, int(incoming_frames))
        else:
            frame_count = len(data["result"])

        # Per-frame accuracy computation
        # Exclude only node-skipped frames (SKIP + llm_time == 0)
        # LLM returning SKIP (llm_time > 0) is a real decision and counts
        results = data["result"]
        llm_times = data.get("llm_time", [])
        ann_brands = data.get("annotation_brands", [])
        ann_colors = data.get("annotation_colors", [])
        ann_plates = data.get("annotation_plates", [])
        ann_actions = data.get("annotation_actions", [])

        def normalize_action(value):
            text = str(value or "").strip().lower()
            if not text:
                return ""
            for sep in [",", ";", "|", "/", "\n", "\t"]:
                text = text.split(sep)[0]
            text = text.strip(" .:!?\"'")
            aliases = {
                "set": "setting",
                "setting": "setting",
                "setter": "setting",
                "spike": "spiking",
                "spiking": "spiking",
                "spiker": "spiking",
                "block": "blocking",
                "blocking": "blocking",
                "blocker": "blocking",
                "dig": "digging",
                "digging": "digging",
                "digger": "digging",
                "jump": "jumping",
                "jumping": "jumping",
                "stand": "standing",
                "standing": "standing",
                "move": "moving",
                "moving": "moving",
                "wait": "waiting",
                "waiting": "waiting",
                "fall": "falling",
                "falling": "falling",
                "other": "other",
            }
            if text in aliases:
                return aliases[text]
            padded = f" {text} "
            for k, v in aliases.items():
                if f" {k} " in padded:
                    return v
            return text

        evaluated = [i for i in range(len(results)) if not (results[i].upper().strip() == "SKIP" and i < len(llm_times) and llm_times[i] == 0)]
        eval_count = len(evaluated)

        brand_matches = sum(1 for i in evaluated if i < len(ann_brands) and results[i].lower().strip() == ann_brands[i].lower().strip()) if ann_brands and ann_brands[0] else None
        color_matches = sum(1 for i in evaluated if i < len(ann_colors) and results[i].lower().strip() == ann_colors[i].lower().strip()) if ann_colors and ann_colors[0] else None
        plate_matches = sum(1 for i in evaluated if i < len(ann_plates) and results[i].upper().strip() == ann_plates[i].upper().strip()) if ann_plates and ann_plates[0] else None

        accuracy = incoming_metrics.get("accuracy", {}) if isinstance(incoming_metrics.get("accuracy"), dict) else {}
        if brand_matches is not None:
            accuracy["brand_accuracy"] = round(brand_matches / eval_count, 4) if eval_count > 0 else 0
        if color_matches is not None:
            accuracy["color_accuracy"] = round(color_matches / eval_count, 4) if eval_count > 0 else 0
        if plate_matches is not None:
            accuracy["plate_accuracy"] = round(plate_matches / eval_count, 4) if eval_count > 0 else 0

        # Volleyball-style action quality metrics
        # - action_match_accuracy: exact normalized action matches on gt-labeled frames
        # - action_recall_micro: micro recall over all gt-labeled frames
        # - action_recall_by_class: recall per GT action class
        pred_norm = {i: normalize_action(results[i]) for i in evaluated}
        gt_norm = {i: normalize_action(ann_actions[i]) for i in evaluated if i < len(ann_actions)}

        gt_labeled_idx = [i for i in evaluated if gt_norm.get(i, "")]
        if gt_labeled_idx:
            action_matches = sum(1 for i in gt_labeled_idx if pred_norm.get(i, "") == gt_norm.get(i, ""))
            accuracy["action_match_accuracy"] = round(action_matches / len(gt_labeled_idx), 4)

        action_recall_by_class = incoming_metrics.get("action_recall_by_class", {})
        if not isinstance(action_recall_by_class, dict):
            action_recall_by_class = {}
        action_recall_micro = incoming_metrics.get("action_recall_micro", None)

        if gt_labeled_idx:
            gt_totals = {}
            tp_totals = {}
            for i in gt_labeled_idx:
                gt_action = gt_norm[i]
                gt_totals[gt_action] = gt_totals.get(gt_action, 0) + 1
                if pred_norm.get(i, "") == gt_action:
                    tp_totals[gt_action] = tp_totals.get(gt_action, 0) + 1

            action_recall_by_class = {
                cls: round(tp_totals.get(cls, 0) / total, 4) if total > 0 else 0
                for cls, total in gt_totals.items()
            }
            tp_sum = sum(tp_totals.values())
            gt_sum = sum(gt_totals.values())
            action_recall_micro = round(tp_sum / gt_sum, 4) if gt_sum > 0 else 0

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
        else:
            if isinstance(incoming_metrics.get("avg_operator_latencies_ms"), dict):
                avg_operator_latencies = incoming_metrics.get("avg_operator_latencies_ms", {})
            elif isinstance(incoming_metrics.get("operator_latencies_ms"), dict):
                avg_operator_latencies = incoming_metrics.get("operator_latencies_ms", {})

            if isinstance(incoming_metrics.get("avg_between_nodes_ms"), dict):
                avg_between_nodes = incoming_metrics.get("avg_between_nodes_ms", {})
            elif isinstance(incoming_metrics.get("between_nodes_ms"), dict):
                avg_between_nodes = incoming_metrics.get("between_nodes_ms", {})

        avg_llm_time_ms = round(sum(data["llm_time"]) / len(data["llm_time"]) * 1000, 2) if data["llm_time"] else incoming_metrics.get("avg_llm_time_ms", 0)
        window_e2e_ms = round((data["in_last"] - data["sent_first"]) * 1000, 2) if "in_last" in data and "sent_first" in data else incoming_metrics.get("window_e2e_ms", 0)

        return {
            "result" : [(v,int(c)) for v,c in zip(result_v, result_c)],
            "sent_first" : data["sent_first"],
            "sent_last" : data["sent_last"],
            "in_first" : data["in_first"],
            "in_last" : data["in_last"],
            "llm_time" : data["llm_time"],
            "llm" : data["llm"],
            "frames" : frame_count,
            "metrics": {
                "accuracy": accuracy,
                "action_recall_micro": action_recall_micro,
                "action_recall_by_class": action_recall_by_class,
                "avg_operator_latencies_ms": avg_operator_latencies,
                "avg_between_nodes_ms": avg_between_nodes,
                "avg_llm_time_ms": avg_llm_time_ms,
                "window_e2e_ms": window_e2e_ms
            }
        }



class MapRemoveLowCount(MapFunction):
    def __init__(self, min_count=3):
        self.min_count = int(min_count)

    def map(self, data):

        return {
            "result" : [x[0] for x in data["result"] if x[1] >= self.min_count],
            "sent_first" : data["sent_first"],
            "sent_last" : data["sent_last"],
            "in_first" : data["in_first"],
            "in_last" : data["in_last"],
            "llm_time" : data["llm_time"],
            "llm" : data["llm"],
            "frames" : data["frames"],
            "metrics": data.get("metrics", {})
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
            def normalize_action(value):
                text = str(value or "").strip().lower()
                if not text:
                    return ""
                for sep in [",", ";", "|", "/", "\n", "\t"]:
                    text = text.split(sep)[0]
                text = text.strip(" .:!?\"'")
                aliases = {
                    "set": "setting",
                    "setting": "setting",
                    "setter": "setting",
                    "spike": "spiking",
                    "spiking": "spiking",
                    "spiker": "spiking",
                    "block": "blocking",
                    "blocking": "blocking",
                    "blocker": "blocking",
                    "dig": "digging",
                    "digging": "digging",
                    "digger": "digging",
                    "jump": "jumping",
                    "jumping": "jumping",
                    "stand": "standing",
                    "standing": "standing",
                    "move": "moving",
                    "moving": "moving",
                    "wait": "waiting",
                    "waiting": "waiting",
                    "fall": "falling",
                    "falling": "falling",
                    "other": "other",
                }
                if text in aliases:
                    return aliases[text]
                padded = f" {text} "
                for k, v in aliases.items():
                    if f" {k} " in padded:
                        return v
                return text

            ann_brand = data.get("annotation_brand", "")
            ann_color = data.get("annotation_color", "")
            ann_plate = data.get("annotation_plate", "")
            ann_action = data.get("annotation_action", "")
            if ann_brand:
                accuracy["brand_match"] = result_val.lower() == ann_brand.lower().strip()
            if ann_color:
                accuracy["color_match"] = result_val.lower() == ann_color.lower().strip()
            if ann_plate:
                accuracy["plate_match"] = result_val.upper() == ann_plate.upper().strip()
            if ann_action:
                accuracy["action_match"] = normalize_action(result_val) == normalize_action(ann_action)

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
  .set_group_id("dashboard_1777149919620_0")\
  .set_topics("volleyball_video")\
  .set_starting_offsets(KafkaOffsetsInitializer.earliest())\
  .set_value_only_deserializer(SimpleStringSchema())\
  .build()

watermark_strategy = WatermarkStrategy.for_bounded_out_of_orderness(Duration.of_seconds(0))\
  .with_timestamp_assigner(lambda e,_: ujson.loads(e)["timestamp"])

stream = env.from_source(kafka_source, watermark_strategy, "Kafka Source")

# Procesing Node 1 (decode)
stream_1 = stream.map(MapDecodeStream())
# Procesing Node 2 (llm)
stream_2 = stream_1.map(MapPromptLLM("""Is there a player blocking at the net in this volleyball image? If yes, return 'blocking'. If not or no players visible, return SKIP.

Do not provide any text or any explanation.""", """qwen2.5-vl-3b"""))
# Procesing Node 3 (window)
stream_3 = stream_2.map(MapChangeFormat()).key_by(lambda _: 0, key_type=Types.INT()).count_window(20).reduce(ReduceWindowResults())
# Procesing Node 4 (filter)
stream_4 = stream_3.map(MapGetCounts()).map(MapRemoveLowCount(3))
# Procesing Node 5 (aggr)
stream_5 = stream_4.map(MapGetCounts())

# Compute metrics (accuracy, latency) before sending to sink
stream_metrics = stream_5.map(MapComputeMetrics("volleyball_repeated_blockers"))

kafka_sink = KafkaSink.builder()\
  .set_bootstrap_servers("kafka:9093")\
  .set_record_serializer(KafkaRecordSerializationSchema.builder()\
       .set_topic("volleyball_repeated_blockers")\
       .set_value_serialization_schema(SimpleStringSchema())\
       .build())\
  .build()

stream_metrics.map(lambda x: ujson.dumps(x)).map(lambda x: x, Types.STRING()).sink_to(kafka_sink)

env.execute("Repeated Blockers (Window)")
