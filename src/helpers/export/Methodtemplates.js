export function generateImports() {
    return `
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
from pyflink.datastream.connectors.kafka import FlinkKafkaConsumer, KafkaSink, KafkaRecordSerializationSchema, KafkaSource
from pyflink.datastream.functions import MapFunction, ReduceFunction, ProcessWindowFunction, ProcessAllWindowFunction, FilterFunction, ProcessFunction
from pyflink.datastream.window import TumblingEventTimeWindows, TumblingProcessingTimeWindows

from llm_call import prompt_llm, send_to_gpt, send_to_ollama

FPS = 20
WINDOW_SIZE = 10
SKIP_AMOUNT = 10
SKIP_COUNTDOWN = -1

### MAP FUNCTIONS #########
`;
}

export function generateGlobalConstants() {
    return `
FPS = 20
WINDOW_SIZE = 10
SKIP_AMOUNT = 10
SKIP_COUNTDOWN = -1

### MAP FUNCTIONS #########
`;
}

export function generateMapDecodeStreamClass() {
    return `
class MapDecodeStream(MapFunction):
    
    def map(self, encoded_data):

        decoded_data = ujson.loads(encoded_data)
        
        # Decode the image  
        decoded_image = base64.b64decode(decoded_data["frame"])
        np_data = np.fromstring(decoded_image,np.uint8)
        image = cv.imdecode(np_data, cv.IMREAD_UNCHANGED)

        return {
            "image" : image,
            #"annotation" : decoded_data["plate"] if decoded_data["brand"] == "renault" and decoded_data["color"] in ["grey", "gray"] else "",
            "sent" : decoded_data["sent"],
            "in" : time.time()
        }

`;
}

export function generateMapResizeImageClass() {
    return `
class MapResizeImage(MapFunction):
    def __init__(self, width_lbound, width_rbound, height_lbound, height_rbound):
        self.width_lbound = width_lbound
        self.width_rbound = width_rbound
        self.height_lbound = height_lbound
        self.height_rbound = height_rbound


    def map(self, data):
        image = data["image"]

        # Select random dimensions within the specified ranges
        width = random.randint(self.width_lbound, self.width_rbound)
        height = random.randint(self.height_lbound, self.height_rbound)

        return {
            # Resize the image using dimensions from the specified ranges
            "image" : cv.resize(image, (width, height), interpolation=cv.INTER_AREA),
           # "annotation" : data["annotation"],
            "sent" : data["sent"],
            "in" : data["in"]
        }

`;
}

export function generateMapPromptLLMClass() {
    return `
class MapPromptLLM(MapFunction):
    def __init__(self, prompt, model="llava"):
        self.prompt = prompt
        self.model = model

    def map(self, data):

        global SKIP_AMOUNT
        global SKIP_COUNTDOWN

        start = time.time()

        # Use the selected model for LLM calls
        if self.model == "gpt-4o-mini":
            answer, llm = send_to_gpt(data["image"], self.prompt)
        else:
            # Use Ollama for all other models
            answer, llm = send_to_ollama(self.model, data["image"], self.prompt)

        end = time.time()

        return {
            "result" : answer.upper().strip(),
           # "annotation" : data["annotation"].upper(),
            "sent" : data["sent"],
            "in" : data["in"],
            "llm_time" : end-start,
            "llm" : llm
        }

`;
}

export function generateMapRecolorImageClass() {
    return `
class MapRecolorImage(MapFunction):
    
    def map(self, data):
        image = data["image"]

        return {
            "image" : cv.cvtColor(image, cv.COLOR_BGR2GRAY),
            #"annotation" : data["annotation"],
            "sent" : data["sent"],
            "in" : data["in"]
        }
`;
}

export function generateFilterNotEmptyClass() {
    return `
class FilterNotEmpty(FilterFunction):
    def filter(self, data):
        return data["result"] != ""

`;
}

export function generateFilterNotSkippedClass() {
    return `
class FilterNotSkipped(FilterFunction):
    def filter(self, data):
        return data["result"].upper() != "SKIPPED"

`;
}

export function generateMapChangeFormatClass() {
    return `
class MapChangeFormat(MapFunction):
    def map(self, data):
        return {
            "result" : [data["result"]],
            #"annotation" : [data["annotation"]],
            "sent_first" : data["sent"],
            "sent_last" : data["sent"],
            "in_first" : data["in"],
            "in_last" : data["in"],
            "llm_time" : [data["llm_time"]],
            "llm" : data["llm"]
        }

`;
}

export function generateReduceWindowResultsClass() {
    return `
class ReduceWindowResults(ReduceFunction):
    def reduce(self, value1, value2):
        return {
            "result" : [*value1["result"], *value2["result"]],
            #"annotation" : [*value1["annotation"], *value2["annotation"]],
            "sent_first" : min(value1["sent_first"], value2["sent_first"]),
            "sent_last" : max(value1["sent_last"], value2["sent_last"]),
            "in_first" : min(value1["in_first"], value2["in_first"]),
            "in_last" : max(value1["in_last"], value2["in_last"]),
            "llm_time" : [*value1["llm_time"], *value2["llm_time"]],
            "llm" : value1["llm"]
        }
            
`;
}

export function generateGrayscaleRecolorMethod() {
    return `
class MapRecolorImage(MapFunction):
    
    def map(self, data):
        image = data["image"]

        return {
            "image" : cv.cvtColor(image, cv.COLOR_BGR2GRAY),
            #"annotation" : data["annotation"],
            "sent" : data["sent"],
            "in" : data["in"]
        }
`;
}

export function generateMapGetCountsMethod() {
    return `

class MapGetCounts(MapFunction):
    def map(self, data):
        
        result_v, result_c = np.unique(data["result"], return_counts=True)
        #annotation_v, annotation_c = np.unique(data["annotation"], return_counts=True)

        return {
            "result" : [(v,c) for v,c in zip(result_v, result_c)],
            #"annotation" : [(v,c) for v,c in zip(annotation_v, annotation_c)],
            "sent_first" : data["sent_first"],
            "sent_last" : data["sent_last"],
            "in_first" : data["in_first"],
            "in_last" : data["in_last"],
            "llm_time" : data["llm_time"],
            "llm" : data["llm"],
            "frames" : len(data["result"])
        }
`;
}

export function generateMapRemoveLowCountMethod() {
    return `
class MapRemoveLowCount(MapFunction):
    def __init__(self, min_count=3):
        self.min_count = int(min_count)

    def map(self, data):

        return {
            "result" : [x[0] for x in data["result"] if x[1] >= self.min_count],
            #"annotation" : [x[0] for x in data["annotation"] if x[1] >= self.min_count],
            "sent_first" : data["sent_first"],
            "sent_last" : data["sent_last"],
            "in_first" : data["in_first"],
            "in_last" : data["in_last"],
            "llm_time" : data["llm_time"],
            "llm" : data["llm"],
            "frames" : data["frames"]
        }
            
`;
}




//# MAP-REDUCE ###

// const templateMap = {
//     MapResizeImage: resizeMethod,
//     MapDecodeStream: decodeNodeMethod,
//     MapPromptLLM: promtLLMMethod,
//     FilterNotSkipped: FilterNotSkippedMethod,
//     FilterNotEmpty: filterRemoveEmptyValues,
//     MapChangeFormat: MapChangeFormat,
//     ReduceWindowResults: ReduceWindowResults,
//     MapRecolorImage: GrayscaleRecolorMethod,
//     MapGetCounts: MapGetCountsMethod,
//     MapRemoveLowCount: MapRemoveLowCountMethod
//     // add any other you want
// };

// Export templates for Python export
// export {
//     generateImports,
//     generateGlobalConstants,
//     generateMapDecodeStreamClass,
//     generateMapResizeImageClass,
//     generateMapPromptLLMClass,
//     generateMapRecolorImageClass,
//     generateFilterNotEmptyClass,
//     generateFilterNotSkippedClass,
//     generateMapChangeFormatClass,
//     generateReduceWindowResultsClass
// };