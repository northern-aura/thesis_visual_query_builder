

export const queries = [

    {
        "title": "Query Car Brand Recognition",
        "nodes": [
            {
                "id": "1",
                "type": "start",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "group_id": "cars",
                    "topic": "cars_video"
                },
                "nextNode": "3",
                "prevNode": null
            },
            {
                "id": "2",
                "type": "end",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "topic": "cars_query_car_color_recognition_optimised_skipping"
                },
                "nextNode": null,
                "prevNode": "6"
            },
            {
                "id": "3",
                "type": "decode",
                "subtype": null,
                "params": {},
                "nextNode": "4",
                "prevNode": "1"
            },
            {
                "id": "4",
                "type": "grayscale",
                "subtype": null,
                "params": {},
                "nextNode": "5",
                "prevNode": "3"
            },
            {
                "id": "5",
                "type": "resize",
                "subtype": null,
                "params": {
                    "width_lbound": "320",
                    "width_rbound": "640",
                    "height_lbound": "180",
                    "height_rbound": "360"
                },
                "nextNode": "6",
                "prevNode": "4"
            },
            {
                "id": "6",
                "type": "llm",
                "subtype": "gemma3:4b",
                "params": {
                    "prompt": "Is there a car visible in this image? If yes, return the color of the car (do not take into consideration the bumper). The answer should be in lowercase and use only primary colors (e.g. black, white, gray, red, blue, etc.), also consider silver to be gray. In case that there are two cars in the frame, return the color of the one which has a visible license plate. If there is no car in the image return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!"
                },
                "nextNode": "2",
                "prevNode": "5"
            }
        ]
    },

    {
        "title": "Query Car Color Recognition",
        "nodes": [
            {
                "id": "1",
                "type": "start",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "group_id": "cars",
                    "topic": "cars_video"
                },
                "nextNode": "3",
                "prevNode": null
            },
            {
                "id": "2",
                "type": "end",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "topic": "cars_query_car_color_recognition_optimised_skipping"
                },
                "nextNode": null,
                "prevNode": "5"
            },
            {
                "id": "3",
                "type": "decode",
                "subtype": null,
                "params": {},
                "nextNode": "4",
                "prevNode": "1"
            },
            {
                "id": "4",
                "type": "resize",
                "subtype": null,
                "params": {
                    "width_lbound": "320",
                    "width_rbound": "640",
                    "height_lbound": "180",
                    "height_rbound": "360"
                },
                "nextNode": "5",
                "prevNode": "3"
            },
            {
                "id": "5",
                "type": "llm",
                "subtype": "gemma3:4b",
                "params": {
                    "prompt": "Is there a car visible in this image? If yes, return the color of the car (do not take into consideration the bumper). The answer should be in lowercase and use only primary colors (e.g. black, white, gray, red, blue, etc.), also consider silver to be gray. In case that there are two cars in the frame, return the color of the one which has a visible license plate. If there is no car in the image return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!"
                },
                "nextNode": "2",
                "prevNode": "4"
            }
        ]
    },
    {
        "title": "Query Grey Renault Plates",
        "nodes": [
            {
                "id": "1",
                "type": "start",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "group_id": "cars",
                    "topic": "cars_video"
                },
                "nextNode": "3",
                "prevNode": null
            },

            {
                "id": "3",
                "type": "decode",
                "subtype": null,
                "params": {},
                "nextNode": "4",
                "prevNode": "1"
            },
            {
                "id": "4",
                "type": "resize",
                "subtype": null,
                "params": {
                    "width_lbound": "320",
                    "width_rbound": "640",
                    "height_lbound": "180",
                    "height_rbound": "360"
                },
                "nextNode": "5",
                "prevNode": "3"
            },
            {
                "id": "5",
                "type": "llm",
                "subtype": "gemma3:4b",
                "params": {
                    "prompt": "Is there a grey (or silver) renault in this image? If yes, return its license plate (in uppercase without any whitespaces). If there is a grey car in the image and you are not sure whether it is a renault or not, return its license plate. If there is no car in the image or you are certain that the car is not a grey renault return the string SKIP.\n\n            Do not provide any text or any explanation, just the final answer in the correct format!"
                },
                "nextNode": "6",
                "prevNode": "4"
            },
            {
                "id": "6",
                "type": "filter",
                "subtype": "remove_empty_values",
                "params": {},
                "nextNode": "7",
                "prevNode": "5"
            },
            {
                "id": "7",
                "type": "filter",
                "subtype": "remove_skipped",
                "params": {},
                "nextNode": "8",
                "prevNode": "6"
            },
            {
                "id": "8",
                "type": "window",
                "subtype": null,
                "params": {
                    "window_size": "10"
                },
                "nextNode": "9",
                "prevNode": "7"
            },
            {
                "id": "9",
                "type": "aggr",
                "subtype": null,
                "params": {},
                "nextNode": "2",
                "prevNode": "8"
            }, {
                "id": "2",
                "type": "end",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "topic": "cars_grey_renault_plates_optimised_skipping"
                },
                "nextNode": null,
                "prevNode": "9"
            }
        ]
    },
    {
        "title": "Query License Plate Recognition",
        "nodes": [
            {
                "id": "1",
                "type": "start",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "group_id": "cars",
                    "topic": "cars_video"
                },
                "nextNode": "3",
                "prevNode": null
            },
            {
                "id": "2",
                "type": "end",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "topic": "cars_query_license_plate_recognition_optimised_skipping"
                },
                "nextNode": null,
                "prevNode": "6"
            },
            {
                "id": "3",
                "type": "decode",
                "subtype": null,
                "params": {},
                "nextNode": "4",
                "prevNode": "1"
            },
            {
                "id": "4",
                "type": "grayscale",
                "subtype": null,
                "params": {},
                "nextNode": "5",
                "prevNode": "3"
            },
            {
                "id": "5",
                "type": "resize",
                "subtype": null,
                "params": {
                    "width_lbound": "320",
                    "width_rbound": "640",
                    "height_lbound": "180",
                    "height_rbound": "360"
                },
                "nextNode": "6",
                "prevNode": "4"
            },
            {
                "id": "6",
                "type": "llm",
                "subtype": "gemma3:4b",
                "params": {
                    "prompt": "Is there a license plate visible in this image? If yes, return the text of the license plate in uppercase without any whitespaces. If there is no license plate in the image, return the string SKIP.\n\n            Do not provide any text or any explanation, just the final answer in the correct format!"
                },
                "nextNode": "2",
                "prevNode": "5"
            }
        ]
    },
    {
        "title": "Query Most Popular Brand",
        "nodes": [
            {
                "id": "1",
                "type": "start",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "group_id": "cars",
                    "topic": "cars_video"
                },
                "nextNode": "3",
                "prevNode": null
            },
            {
                "id": "2",
                "type": "end",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "topic": "cars_query_most_popular_brand_optimised_skipping"
                },
                "nextNode": null,
                "prevNode": "10"
            },

            {
                "id": "3",
                "type": "decode",
                "subtype": null,
                "params": {},
                "nextNode": "4",
                "prevNode": "1"
            },
            {
                "id": "4",
                "type": "grayscale",
                "subtype": null,
                "params": {},
                "nextNode": "5",
                "prevNode": "3"
            },
            {
                "id": "5",
                "type": "resize",
                "subtype": null,
                "params": {
                    "width_lbound": "320",
                    "width_rbound": "640",
                    "height_lbound": "180",
                    "height_rbound": "360"
                },
                "nextNode": "6",
                "prevNode": "4"
            },
            {
                "id": "6",
                "type": "llm",
                "subtype": "gemma3:4b",
                "params": {
                    "prompt": "Is there a car visible in this image? If yes, return the brand of the car. The answer should be in lowercase and ignore any umlaut (e.g. citroen). In case that there are two cars in the frame, return the brand of the one which has a visible license plate. If there is no car in the image or you cannot identify the brand, return the string SKIP.\n\n            Do not provide any text or any explanation, just the final answer in the correct format!"
                },
                "nextNode": "7",
                "prevNode": "5"
            },
            {
                "id": "7",
                "type": "filter",
                "subtype": "remove_empty_values",
                "params": {},
                "nextNode": "8",
                "prevNode": "6"
            },
            {
                "id": "8",
                "type": "filter",
                "subtype": "remove_skipped",
                "params": {},
                "nextNode": "9",
                "prevNode": "7"
            },
            {
                "id": "9",
                "type": "window",
                "subtype": null,
                "params": {
                    "window_size": "10"
                },
                "nextNode": "10",
                "prevNode": "8"
            },
            {
                "id": "10",
                "type": "aggr",
                "subtype": null,
                "params": {},
                "nextNode": "2",
                "prevNode": "9"
            }
        ]
    }, {
        "title": "Query Most Popular Color + Brand",
        "nodes": [
            {
                "id": "1",
                "type": "start",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "group_id": "cars",
                    "topic": "cars_video"
                },
                "nextNode": "3",
                "prevNode": null
            },
            {
                "id": "2",
                "type": "end",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "topic": "cars_query_most_popular_brand_optimised_skipping"
                },
                "nextNode": null,
                "prevNode": "10"
            },
            {
                "id": "3",
                "type": "decode",
                "subtype": null,
                "params": {},
                "nextNode": "5",
                "prevNode": "1"
            },

            {
                "id": "5",
                "type": "resize",
                "subtype": null,
                "params": {
                    "width": "640",
                    "height": "360"
                },
                "nextNode": "6",
                "prevNode": "3"
            },
            {
                "id": "6",
                "type": "llm",
                "subtype": "gemma3:4b",
                "params": {
                    "prompt": "Is there a car visible in this image? If yes, return the color of the car (do not take into consideration the bumper) and its brand. The answer should be in lowercase and use only primary colors (e.g. black, white, gray, red, blue, etc.), also consider silver to be gray. Separate the color and the brand with a comma only, do not use any whitespace. In case that there are two cars in the frame return the color and the brand of the one which has a visible license plate. If there is no car in the image return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!"
                },
                "nextNode": "7",
                "prevNode": "5"
            },
            {
                "id": "7",
                "type": "filter",
                "subtype": "remove_empty_values",
                "params": {},
                "nextNode": "8",
                "prevNode": "6"
            },
            {
                "id": "8",
                "type": "filter",
                "subtype": "remove_skipped",
                "params": {},
                "nextNode": "9",
                "prevNode": "7"
            },
            {
                "id": "9",
                "type": "window",
                "subtype": null,
                "params": {
                    "window_size": "10"
                },
                "nextNode": "10",
                "prevNode": "8"
            },
            {
                "id": "10",
                "type": "aggr",
                "subtype": null,
                "params": {},
                "nextNode": "2",
                "prevNode": "9"
            }
        ]
    },
    {
        "title": "Query Most Popular Color",
        "nodes": [
            {
                "id": "1",
                "type": "start",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "group_id": "cars",
                    "topic": "cars_video"
                },
                "nextNode": "3",
                "prevNode": null
            },
            {
                "id": "2",
                "type": "end",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "topic": "cars_query_most_popular_color_optimised_skipping"
                },
                "nextNode": null,
                "prevNode": "9"
            },
            {
                "id": "3",
                "type": "decode",
                "subtype": null,
                "params": {},
                "nextNode": "4",
                "prevNode": "1"
            },
            {
                "id": "4",
                "type": "resize",
                "subtype": null,
                "params": {
                    "width_lbound": "320",
                    "width_rbound": "640",
                    "height_lbound": "180",
                    "height_rbound": "360"
                },
                "nextNode": "5",
                "prevNode": "3"
            },
            {
                "id": "5",
                "type": "llm",
                "subtype": "gemma3:4b",
                "params": {
                    "prompt": "Is there a car visible in this image? If yes, return the color of the car (do not take into consideration the bumper). The answer should be in lowercase and use only primary colors (e.g. black, white, gray, red, blue, etc.), also consider silver to be gray. In case that there are two cars in the frame, return the color of the one which has a visible license plate. If there is no car in the image return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!"
                },
                "nextNode": "6",
                "prevNode": "4"
            },
            {
                "id": "6",
                "type": "filter",
                "subtype": "remove_empty_values",
                "params": {},
                "nextNode": "7",
                "prevNode": "5"
            },
            {
                "id": "7",
                "type": "filter",
                "subtype": "remove_skipped",
                "params": {},
                "nextNode": "8",
                "prevNode": "6"
            },
            {
                "id": "8",
                "type": "window",
                "subtype": null,
                "params": {
                    "window_size": "10"
                },
                "nextNode": "9",
                "prevNode": "7"
            },

            {
                "id": "9",
                "type": "aggr",
                "subtype": null,
                "params": {},
                "nextNode": "2",
                "prevNode": "8"
            }
        ]
    },
    {
        "title": "Query Repeating License Plates",
        "nodes": [
            {
                "id": "1",
                "type": "start",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "group_id": "cars",
                    "topic": "cars_video"
                },
                "nextNode": "3",
                "prevNode": null
            },
            {
                "id": "2",
                "type": "end",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "topic": "cars_query_repeating_license_plates_optimised_skipping"
                },
                "nextNode": null,
                "prevNode": "12"
            },
            {
                "id": "3",
                "type": "decode",
                "subtype": null,
                "params": {},
                "nextNode": "4",
                "prevNode": "1"
            },
            {
                "id": "4",
                "type": "grayscale",
                "subtype": null,
                "params": {},
                "nextNode": "5",
                "prevNode": "3"
            },
            {
                "id": "5",
                "type": "resize",
                "subtype": null,
                "params": { "width_lbound": "320", "width_rbound": "640", "height_lbound": "180", "height_rbound": "360" },
                "nextNode": "6",
                "prevNode": "4"
            },
            {
                "id": "6",
                "type": "llm",
                "subtype": "gemma3:4b",
                "params": {
                    "prompt": "Based on this image, is there a license plate visible in the image? If yes, return the text of the license plate in uppercase without any whitespaces. If there is no license plate in the image, return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!"
                },
                "nextNode": "7",
                "prevNode": "5"
            },
            {
                "id": "7",
                "type": "filter",
                "subtype": "remove_empty_values",
                "params": {},
                "nextNode": "8",
                "prevNode": "6"
            },
            {
                "id": "8",
                "type": "filter",
                "subtype": "remove_skipped",
                "params": {},
                "nextNode": "9",
                "prevNode": "7"
            },
            {
                "id": "9",
                "type": "window",
                "subtype": null,
                "params": { "window_size": "10" },
                "nextNode": "11",
                "prevNode": "8"
            },

            {
                "id": "11",
                "type": "filter",
                "subtype": "remove_count_less_than",
                "params": { "Remove Values Less Than": "3" },   // M = 3
                "nextNode": "12",
                "prevNode": "9"
            },
            {
                "id": "12",
                "type": "aggr",
                "subtype": "distinct",
                "params": {},
                "nextNode": "2",
                "prevNode": "11"
            }
        ]
    },
    {
        "title": "Query Unique License Plates Optimised Skipping",
        "nodes": [
            {
                "id": "1",
                "type": "start",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "group_id": "cars",
                    "topic": "cars_video"
                },
                "nextNode": "3",
                "prevNode": null
            },
            {
                "id": "3",
                "type": "decode",
                "subtype": null,
                "params": {},
                "nextNode": "4",
                "prevNode": "1"
            },
            {
                "id": "4",
                "type": "grayscale",
                "subtype": null,
                "params": {},
                "nextNode": "5",
                "prevNode": "3"
            },
            {
                "id": "5",
                "type": "resize",
                "subtype": null,
                "params": {
                    "width_lbound": "320",
                    "width_rbound": "640",
                    "height_lbound": "180",
                    "height_rbound": "360"
                },
                "nextNode": "6",
                "prevNode": "4"
            },
            {
                "id": "6",
                "type": "llm",
                "subtype": "gemma3:4b",
                "params": {
                    "prompt": "Based on this image, is there a license plate visible in the image? If yes, return the text of the license plate in uppercase without any whitespaces. If there is no license plate in the image, return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!"
                },
                "nextNode": "7",
                "prevNode": "5"
            },
            {
                "id": "7",
                "type": "filter",
                "subtype": "remove_empty_values",
                "params": {
                    "subtype": "remove_empty_values"
                },
                "nextNode": "8",
                "prevNode": "6"
            },
            {
                "id": "8",
                "type": "filter",
                "subtype": "remove_skipped",
                "params": {
                    "subtype": "remove_skipped"
                },
                "nextNode": "9",
                "prevNode": "7"
            },
            {
                "id": "9",
                "type": "window",
                "subtype": null,
                "params": {
                    "window_size": "10"
                },
                "nextNode": "12",
                "prevNode": "8"
            },
            {
                "id": "12",
                "type": "aggr",
                "subtype": null,
                "params": {},
                "nextNode": "2",
                "prevNode": "9"
            },
            {
                "id": "2",
                "type": "end",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "topic": "cars_query_repeating_license_plates_optimised_skipping"
                },
                "nextNode": null,
                "prevNode": "12"
            }
        ]
    },
    {
        "title": "Query Repeating License Plates",
        "nodes": [
            {
                "id": "1",
                "type": "start",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "group_id": "cars",
                    "topic": "cars_video"
                },
                "nextNode": "3",
                "prevNode": null
            },
            {
                "id": "2",
                "type": "end",
                "subtype": null,
                "params": {
                    "server": "localhost:9092",
                    "topic": "cars_query_repeating_license_plates_optimised_skipping"
                },
                "nextNode": null,
                "prevNode": "12"
            },
            {
                "id": "3",
                "type": "decode",
                "subtype": null,
                "params": {},
                "nextNode": "4",
                "prevNode": "1"
            },
            {
                "id": "4",
                "type": "grayscale",
                "subtype": null,
                "params": {},
                "nextNode": "5",
                "prevNode": "3"
            },
            {
                "id": "5",
                "type": "resize",
                "subtype": null,
                "params": { "width_lbound": "320", "width_rbound": "640", "height_lbound": "180", "height_rbound": "360" },
                "nextNode": "6",
                "prevNode": "4"
            },
            {
                "id": "6",
                "type": "llm",
                "subtype": "gemma3:4b",
                "params": {
                    "prompt": "Is there a car visible in this image? If yes, return the color of the car, but only if it is not black or white, (do not take into consideration the bumper). The answer should be in lowercase and use only primary colors (e.g. gray, red, blue, etc.), also consider silver to be gray. In case that there are two cars in the frame, return the color of the one which has a visible license plate. If there is no car in the image, or the color is black or white return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!"
                },
                "nextNode": "7",
                "prevNode": "5"
            },
            {
                "id": "7",
                "type": "filter",
                "subtype": "remove_empty_values",
                "params": {},
                "nextNode": "8",
                "prevNode": "6"
            },
            {
                "id": "8",
                "type": "filter",
                "subtype": "remove_skipped",
                "params": {},
                "nextNode": "9",
                "prevNode": "7"
            },
            {
                "id": "9",
                "type": "window",
                "subtype": null,
                "params": { "window_size": "10" },
                "nextNode": "11",
                "prevNode": "8"
            },

            {
                "id": "11",
                "type": "filter",
                "subtype": "remove_count_less_than",
                "params": { "Remove Values Less Than": "3" },   // M = 3
                "nextNode": "12",
                "prevNode": "9"
            },
            {
                "id": "12",
                "type": "aggr",
                "subtype": "distinct",
                "params": {},
                "nextNode": "2",
                "prevNode": "11"
            }
        ]
    },




]