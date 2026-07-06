

// Helper: common Kafka source for cars dataset
const carsSource = (nextNode) => ({
    "id": "1", "type": "start", "subtype": null,
    "params": { "server": "localhost:9092", "group_id": "cars", "topic": "cars_video" },
    "nextNode": nextNode, "prevNode": null
});

// Helper: common Kafka source for volleyball dataset
const volleyballSource = (nextNode) => ({
    "id": "1", "type": "start", "subtype": null,
    "params": { "server": "localhost:9092", "group_id": "volleyball", "topic": "volleyball_video" },
    "nextNode": nextNode, "prevNode": null
});

const carsSink = (topic, prevNode) => ({
    "id": "2", "type": "end", "subtype": null,
    "params": { "server": "localhost:9092", "topic": topic },
    "nextNode": null, "prevNode": prevNode
});

const decodeNode = (nextNode, prevNode) => ({
    "id": "3", "type": "decode", "subtype": null, "params": {},
    "nextNode": nextNode, "prevNode": prevNode
});

const grayscaleNode = (id, nextNode, prevNode) => ({
    "id": id, "type": "grayscale", "subtype": null, "params": {},
    "nextNode": nextNode, "prevNode": prevNode
});

const resizeNode = (id, nextNode, prevNode, width = "640", height = "360") => ({
    "id": id, "type": "resize", "subtype": null,
    "params": { "width": width, "height": height },
    "nextNode": nextNode, "prevNode": prevNode
});

const llmNode = (id, prompt, nextNode, prevNode, subtype = "qwen2.5-vl-7b") => ({
    "id": id, "type": "llm", "subtype": subtype,
    "params": { "prompt": prompt },
    "nextNode": nextNode, "prevNode": prevNode
});

const windowNode = (id, nextNode, prevNode, size = "30") => ({
    "id": id, "type": "window", "subtype": null,
    "params": { "window_size": size },
    "nextNode": nextNode, "prevNode": prevNode
});

const aggrNode = (id, nextNode, prevNode, subtype = null) => ({
    "id": id, "type": "aggr", "subtype": subtype, "params": {},
    "nextNode": nextNode, "prevNode": prevNode
});

const filterCountLessThan = (id, nextNode, prevNode, threshold = "3") => ({
    "id": id, "type": "filter", "subtype": "remove_count_less_than",
    "params": { "Remove Values Less Than": threshold },
    "nextNode": nextNode, "prevNode": prevNode
});

const cvColorFilterNode = (id, colorSubtype, nextNode, prevNode, threshold = "5") => ({
    "id": id, "type": "cv_color_filter", "subtype": colorSubtype,
    "params": { "threshold": threshold },
    "nextNode": nextNode, "prevNode": prevNode
});

const skipFramesNode = (id, skipOnEmpty, skipOnDetect, nextNode, prevNode) => ({
    "id": id, "type": "skip_frames", "subtype": null,
    "params": { "skip_on_empty": skipOnEmpty, "skip_on_detect": skipOnDetect },
    "nextNode": nextNode, "prevNode": prevNode
});

const frameBatcherNode = (id, batchSize, nextNode, prevNode) => ({
    "id": id, "type": "frame_batcher", "subtype": null,
    "params": { "batch_size": batchSize },
    "nextNode": nextNode, "prevNode": prevNode
});

const completedOptimizedResultTitles = new Set([
    "Optimized Car Brand Generic (R854)",
    "Optimized Car Color Generic (R480)",
    "Optimized Car Color Red (CFred+R480)",
    "Optimized Color+Plate Red (CFred native)",
    "Optimized Motion Category (R480)"
]);

const bestOptimizedQuery = (query, changedThisTurn = false) => ({
    ...query,
    meta: {
        ...(query.meta || {}),
        bestOptimized: true,
        changedThisTurn,
        needsRun: !completedOptimizedResultTitles.has(query.title)
    }
});


// ==================== Shared Prompts ====================

const PROMPTS = {
    brandGeneric: "Is there a car visible in this image? If yes, return the brand of the car in lowercase (e.g. ford, renault, toyota, bmw). Ignore any umlauts (e.g. citroen). In case that there are two cars in the frame, return the brand of the one which has a visible license plate. If there is no car in the image or you cannot identify the brand, return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    brandFord: "Is there a car visible in this image? If yes, is it a Ford? If it is a Ford, return \"ford\". If the car is not a Ford or there is no car, return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    brandRenault: "Is there a car visible in this image? If yes, is it a Renault? If it is a Renault, return \"renault\". If the car is not a Renault or there is no car, return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    brandToyota: "Is there a car visible in this image? If yes, is it a Toyota? If it is a Toyota, return \"toyota\". If the car is not a Toyota or there is no car, return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    colorGeneric: "Is there a car visible in this image? If yes, return the color of the car (do not take into consideration the bumper). The answer should be in lowercase and use only primary colors (e.g. black, white, gray, red, blue, etc.), also consider silver to be gray. In case that there are two cars in the frame, return the color of the one which has a visible license plate. If there is no car in the image return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    colorRed: "Is there a car visible in this image? If yes, is the car red (do not take into consideration the bumper)? If the car is red, return \"red\". If the car is not red or there is no car, return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    colorGrey: "Is there a car visible in this image? If yes, is the car gray or silver (do not take into consideration the bumper)? If the car is gray or silver, return \"gray\". If the car is not gray/silver or there is no car, return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    colorWhite: "Is there a car visible in this image? If yes, is the car white (do not take into consideration the bumper)? If the car is white, return \"white\". If the car is not white or there is no car, return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    colorBlue: "Is there a car visible in this image? If yes, is the car blue (do not take into consideration the bumper)? If the car is blue, return \"blue\". If the car is not blue or there is no car, return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    plateGeneric: "Is there a license plate visible in this image? If yes, return the text of the license plate in uppercase without any whitespaces. If there is no license plate in the image, return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    plateSpecific: "Is there a license plate visible in this image? If yes, read the license plate text. If the license plate reads \"QRF8G17\" (ignoring whitespace), return \"QRF8G17\". Otherwise, return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    colorPlateRed: "Is there a car visible in this image? If yes, is the car red (do not take into consideration the bumper)? If the car is red, return its license plate in uppercase without any whitespaces. If the car is not red or there is no car or no license plate is visible, return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    mostPopularBrand: "Is there a car visible in this image? If yes, return the brand of the car. The answer should be in lowercase and ignore any umlaut (e.g. citroen). In case that there are two cars in the frame, return the brand of the one which has a visible license plate. If there is no car in the image or you cannot identify the brand, return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    mostPopularBrandColor: "Is there a car visible in this image? If yes, return the color of the car (do not take into consideration the bumper) and its brand. The answer should be in lowercase and use only primary colors (e.g. black, white, gray, red, blue, etc.), also consider silver to be gray. Separate the color and the brand with a comma only, do not use any whitespace. In case that there are two cars in the frame return the color and the brand of the one which has a visible license plate. If there is no car in the image return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    mostPopularColorFord: "Is there a car visible in this image? If yes, is it a Ford? If it is a Ford, return the color of the car in lowercase using only primary colors (e.g. black, white, gray, red, blue, etc.), also consider silver to be gray. Do not take into consideration the bumper. If it is not a Ford or there is no car, return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    mostPopularBrandRed: "Is there a car visible in this image? If yes, is the car red (do not take into consideration the bumper)? If the car is red, return the brand of the car in lowercase (e.g. ford, renault, toyota, bmw). If the car is not red or there is no car, return the string SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    // --- Volleyball ---
    vbActionGeneric: "Look at this volleyball image. What is the dominant player action? Reply with exactly one of: waiting, setting, digging, falling, jumping, moving, blocking, standing, spiking. If no players are visible, return SKIP.\n\nDo not provide any text or any explanation, just the final answer in the correct format!",

    vbSpiking: "Is there a player spiking the ball in this volleyball image? If yes, return 'spiking'. If not or no players visible, return SKIP.\n\nDo not provide any text or any explanation.",
    vbSetting: "Is there a player setting the ball in this volleyball image? If yes, return 'setting'. If not or no players visible, return SKIP.\n\nDo not provide any text or any explanation.",
    vbBlocking: "Is there a player blocking at the net in this volleyball image? If yes, return 'blocking'. If not or no players visible, return SKIP.\n\nDo not provide any text or any explanation.",
    vbDigging: "Is there a player digging the ball in this volleyball image? If yes, return 'digging'. If not or no players visible, return SKIP.\n\nDo not provide any text or any explanation.",
    vbJumping: "Is there a player jumping in this volleyball image? If yes, return 'jumping'. If not or no players visible, return SKIP.\n\nDo not provide any text or any explanation.",
    vbMoving: "Are there players moving (running) in this volleyball image? Return 'moving' if at least one player is moving, otherwise SKIP.\n\nDo not provide any text or any explanation.",
    vbStanding: "Are there players standing still in this volleyball image? Return 'standing' if at least one player is standing, otherwise SKIP.\n\nDo not provide any text or any explanation.",

    vbMotionCategory: "Look at this volleyball image. Roughly what fraction of visible players are moving (running/jumping/diving) vs. standing still? Reply with exactly one of: ALL_MOVING, MOST_MOVING, SOME_MOVING, NONE_MOVING. If no players visible, return SKIP.\n\nDo not provide any text or any explanation.",

    // Sequence detection — short labels so window aggregation can detect ordering downstream
    vbSetSpike: "Look at this volleyball image. Is the dominant action setting, spiking, or neither? Reply with one of: set, spike, other. If no players visible, return SKIP.\n\nDo not provide any text or any explanation.",
    vbSetBlock: "Look at this volleyball image. Is the dominant action setting, blocking, or neither? Reply with one of: set, block, other. If no players visible, return SKIP.\n\nDo not provide any text or any explanation.",
    vbDigSet: "Look at this volleyball image. Is the dominant action digging, setting, or neither? Reply with one of: dig, set, other. If no players visible, return SKIP.\n\nDo not provide any text or any explanation.",
    vbJumpSpike: "Look at this volleyball image. Is the dominant action jumping, spiking, or neither? Reply with one of: jump, spike, other. If no players visible, return SKIP.\n\nDo not provide any text or any explanation.",

    // Bounding boxes
    vbBboxSpike: "Is a volleyball spike happening in this image? If yes, return the bounding box of the spiking player as 'x1,y1,x2,y2' (pixel integers). If no spike, return SKIP.\n\nDo not provide any text or any explanation.",
    vbBboxBlock: "Is a volleyball block happening at the net in this image? If yes, return the bounding box of the blocking player as 'x1,y1,x2,y2' (pixel integers). If no block, return SKIP.\n\nDo not provide any text or any explanation.",
    vbBboxSet: "Is a volleyball set happening in this image? If yes, return the bounding box of the setting player as 'x1,y1,x2,y2' (pixel integers). If no set, return SKIP.\n\nDo not provide any text or any explanation.",
    vbBboxDig: "Is a volleyball dig happening in this image? If yes, return the bounding box of the digging player as 'x1,y1,x2,y2' (pixel integers). If no dig, return SKIP.\n\nDo not provide any text or any explanation.",
};


export const queryGroups = [

    // ==================== BLOCK 1: Naive Queries (no preprocessing) ====================
    {
        dataset: "Naive",
        runnable: true,
        senderScript: "running/Topics/Cars/Data/send_video.py",
        queries: [

            // --- Per-frame: Source -> Decode -> LLM -> Sink ---

            {
                "title": "Car Brand (Generic)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_brand_generic", "4"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.brandGeneric, "2", "3")
                ]
            },

            {
                "title": "Car Brand Ford",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_brand_ford", "4"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.brandFord, "2", "3")
                ]
            },

            {
                "title": "Car Brand Renault",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_brand_renault", "4"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.brandRenault, "2", "3")
                ]
            },

            {
                "title": "Car Brand Toyota",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_brand_toyota", "4"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.brandToyota, "2", "3")
                ]
            },

            {
                "title": "Car Color (Generic)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_color_generic", "4"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.colorGeneric, "2", "3")
                ]
            },

            {
                "title": "Car Color Red",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_color_red", "4"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.colorRed, "2", "3")
                ]
            },

            {
                "title": "Car Color Grey",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_color_grey", "4"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.colorGrey, "2", "3")
                ]
            },

            {
                "title": "Car Color White",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_color_white", "4"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.colorWhite, "2", "3")
                ]
            },

            {
                "title": "Car Color Blue",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_color_blue", "4"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.colorBlue, "2", "3")
                ]
            },

            {
                "title": "License Plate Recognition (Generic)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_plate_generic", "4"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.plateGeneric, "2", "3")
                ]
            },

            {
                "title": "Specific Plate: QRF8G17",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_specific_plate_qrf8g17", "4"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.plateSpecific, "2", "3")
                ]
            },

            {
                "title": "Color + License Plate (Red)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_color_plate_red", "4"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.colorPlateRed, "2", "3")
                ]
            },

            // --- Windowed: Source -> Decode -> LLM -> Window -> Aggr -> Sink ---

            {
                "title": "Most Popular Brand",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_most_popular_brand", "8"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.mostPopularBrand, "7", "3"),
                    windowNode("7", "8", "4"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Most Popular Color",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_most_popular_color", "8"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.colorGeneric, "7", "3"),
                    windowNode("7", "8", "4"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Most Popular Brand and Color",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_most_popular_brand_and_color", "8"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.mostPopularBrandColor, "7", "3"),
                    windowNode("7", "8", "4"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Most Popular Color (Ford)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_most_popular_color_ford", "8"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.mostPopularColorFord, "7", "3"),
                    windowNode("7", "8", "4"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Most Popular Brand (Red Cars)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_most_popular_brand_red", "8"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.mostPopularBrandRed, "7", "3"),
                    windowNode("7", "8", "4"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Unique License Plates (Window)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_unique_plates_window", "8"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.plateGeneric, "7", "3"),
                    windowNode("7", "8", "4"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Repeating License Plates",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_repeating_plates", "9"),
                    decodeNode("4", "1"),
                    llmNode("4", PROMPTS.plateGeneric, "7", "3"),
                    windowNode("7", "8", "4"),
                    filterCountLessThan("8", "9", "7", "3"),
                    aggrNode("9", "2", "8", "distinct")
                ]
            },

        ]
    },

    // ==================== BLOCK 2: Optimized Queries (systematic preprocessing) ====================
    {
        dataset: "Optimized",
        runnable: true,
        senderScript: "running/Topics/Cars/Data/send_video.py",
        queries: [

            // --- Brand Recognition ---

            {
                "title": "Car Brand (Resize)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_brand_resize", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.brandGeneric, "2", "4")
                ]
            },

            {
                "title": "Car Brand (Skip 10)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_brand_skip10", "5"),
                    decodeNode("4", "1"),
                    skipFramesNode("4", "10", "0", "5", "3"),
                    llmNode("5", PROMPTS.brandGeneric, "2", "4")
                ]
            },

            // --- Color Recognition ---

            {
                "title": "Car Color (Resize)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_color_resize", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.colorGeneric, "2", "4")
                ]
            },

            {
                "title": "Car Color (Skip 10)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_color_skip10", "5"),
                    decodeNode("4", "1"),
                    skipFramesNode("4", "10", "0", "5", "3"),
                    llmNode("5", PROMPTS.colorGeneric, "2", "4")
                ]
            },

            // --- License Plate Recognition ---

            {
                "title": "License Plate Recognition (Resize)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_plate_resize", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "960", "540"),
                    llmNode("5", PROMPTS.plateGeneric, "2", "4")
                ]
            },

            {
                "title": "License Plate Recognition (Skip 10)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_plate_skip10", "5"),
                    decodeNode("4", "1"),
                    skipFramesNode("4", "10", "0", "5", "3"),
                    llmNode("5", PROMPTS.plateGeneric, "2", "4")
                ]
            },

            {
                "title": "License Plate Recognition (Grayscale)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_plate_grayscale", "6"),
                    decodeNode("4", "1"),
                    grayscaleNode("4", "5", "3"),
                    resizeNode("5", "6", "4", "960", "540"),
                    llmNode("6", PROMPTS.plateGeneric, "2", "5")
                ]
            },

            // --- Specific Plate Recognition ---

            {
                "title": "Specific Plate (Resize)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_specific_plate_resize", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "960", "540"),
                    llmNode("5", PROMPTS.plateSpecific, "2", "4")
                ]
            },

            {
                "title": "Specific Plate (Skip 10)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_specific_plate_skip10", "5"),
                    decodeNode("4", "1"),
                    skipFramesNode("4", "10", "0", "5", "3"),
                    llmNode("5", PROMPTS.plateSpecific, "2", "4")
                ]
            },

            {
                "title": "Specific Plate (Grayscale)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_specific_plate_grayscale", "6"),
                    decodeNode("4", "1"),
                    grayscaleNode("4", "5", "3"),
                    resizeNode("5", "6", "4", "960", "540"),
                    llmNode("6", PROMPTS.plateSpecific, "2", "5")
                ]
            },

            // --- Color + License Plate ---

            {
                "title": "Color + Plate (Resize)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_color_plate_resize", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "960", "540"),
                    llmNode("5", PROMPTS.colorPlateRed, "2", "4")
                ]
            },

            {
                "title": "Color + Plate (Skip 10)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_color_plate_skip10", "5"),
                    decodeNode("4", "1"),
                    skipFramesNode("4", "10", "0", "5", "3"),
                    llmNode("5", PROMPTS.colorPlateRed, "2", "4")
                ]
            },

            // --- Windowed Brand ---

            {
                "title": "Most Popular Brand (Resize)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_most_popular_brand_resize", "8"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.mostPopularBrand, "7", "4"),
                    windowNode("7", "8", "5"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Most Popular Brand (Skip 10)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_most_popular_brand_skip10", "8"),
                    decodeNode("4", "1"),
                    skipFramesNode("4", "10", "0", "5", "3"),
                    llmNode("5", PROMPTS.mostPopularBrand, "7", "4"),
                    windowNode("7", "8", "5"),
                    aggrNode("8", "2", "7")
                ]
            },

            // --- Windowed Color ---

            {
                "title": "Most Popular Color (Resize)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_most_popular_color_resize", "8"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.colorGeneric, "7", "4"),
                    windowNode("7", "8", "5"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Most Popular Color (Skip 10)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_most_popular_color_skip10", "8"),
                    decodeNode("4", "1"),
                    skipFramesNode("4", "10", "0", "5", "3"),
                    llmNode("5", PROMPTS.colorGeneric, "7", "4"),
                    windowNode("7", "8", "5"),
                    aggrNode("8", "2", "7")
                ]
            },

            // --- Windowed Brand + Color ---

            {
                "title": "Most Popular Brand+Color (Resize)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_most_popular_brand_color_resize", "8"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.mostPopularBrandColor, "7", "4"),
                    windowNode("7", "8", "5"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Most Popular Brand+Color (Skip 10)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_most_popular_brand_color_skip10", "8"),
                    decodeNode("4", "1"),
                    skipFramesNode("4", "10", "0", "5", "3"),
                    llmNode("5", PROMPTS.mostPopularBrandColor, "7", "4"),
                    windowNode("7", "8", "5"),
                    aggrNode("8", "2", "7")
                ]
            },

            // --- Windowed Unique Plates ---

            {
                "title": "Unique Plates (Resize)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_unique_plates_resize", "8"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "960", "540"),
                    llmNode("5", PROMPTS.plateGeneric, "7", "4"),
                    windowNode("7", "8", "5"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Unique Plates (Skip 10)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_unique_plates_skip10", "8"),
                    decodeNode("4", "1"),
                    skipFramesNode("4", "10", "0", "5", "3"),
                    llmNode("5", PROMPTS.plateGeneric, "7", "4"),
                    windowNode("7", "8", "5"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Unique Plates (Grayscale)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_unique_plates_grayscale", "9"),
                    decodeNode("4", "1"),
                    grayscaleNode("4", "5", "3"),
                    resizeNode("5", "6", "4", "960", "540"),
                    llmNode("6", PROMPTS.plateGeneric, "8", "5"),
                    windowNode("8", "9", "6"),
                    aggrNode("9", "2", "8")
                ]
            },

            // --- Windowed Repeating Plates ---

            {
                "title": "Repeating Plates (Resize)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_repeating_plates_resize", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "960", "540"),
                    llmNode("5", PROMPTS.plateGeneric, "7", "4"),
                    windowNode("7", "8", "5"),
                    filterCountLessThan("8", "9", "7", "3"),
                    aggrNode("9", "2", "8", "distinct")
                ]
            },

            {
                "title": "Repeating Plates (Skip 10)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_repeating_plates_skip10", "9"),
                    decodeNode("4", "1"),
                    skipFramesNode("4", "10", "0", "5", "3"),
                    llmNode("5", PROMPTS.plateGeneric, "7", "4"),
                    windowNode("7", "8", "5"),
                    filterCountLessThan("8", "9", "7", "3"),
                    aggrNode("9", "2", "8", "distinct")
                ]
            },

            {
                "title": "Repeating Plates (Grayscale)",
                "nodes": [
                    carsSource("3"),
                    carsSink("cars_repeating_plates_grayscale", "10"),
                    decodeNode("4", "1"),
                    grayscaleNode("4", "5", "3"),
                    resizeNode("5", "6", "4", "960", "540"),
                    llmNode("6", PROMPTS.plateGeneric, "8", "5"),
                    windowNode("8", "9", "6"),
                    filterCountLessThan("9", "10", "8", "3"),
                    aggrNode("10", "2", "9", "distinct")
                ]
            },

        ]
    },

    // ==================== BLOCK 3: Volleyball Naive (temporal queries with Frame Batcher) ====================
    {
        dataset: "Volleyball (Naive)",
        runnable: true,
        senderScript: "running/Topics/Volleyball/Data/send_volleyball.py",
        queries: [

            // --- Task 2: Action-state Repetition ---

            {
                "title": "Repeated Spikers (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_repeated_spikers", "9"),
                    decodeNode("5", "1"),
                    llmNode("5", PROMPTS.vbSpiking, "7", "3"),
                    windowNode("7", "8", "5", "20f"),
                    filterCountLessThan("8", "9", "7", "3"),
                    aggrNode("9", "2", "8", "distinct")
                ]
            },

            {
                "title": "Repeated Setters (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_repeated_setters", "9"),
                    decodeNode("5", "1"),
                    llmNode("5", PROMPTS.vbSetting, "7", "3"),
                    windowNode("7", "8", "5", "20f"),
                    filterCountLessThan("8", "9", "7", "3"),
                    aggrNode("9", "2", "8", "distinct")
                ]
            },

            {
                "title": "Repeated Blockers (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_repeated_blockers", "9"),
                    decodeNode("5", "1"),
                    llmNode("5", PROMPTS.vbBlocking, "7", "3"),
                    windowNode("7", "8", "5", "20f"),
                    filterCountLessThan("8", "9", "7", "3"),
                    aggrNode("9", "2", "8", "distinct")
                ]
            },

            {
                "title": "Repeated Diggers (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_repeated_diggers", "9"),
                    decodeNode("5", "1"),
                    llmNode("5", PROMPTS.vbDigging, "7", "3"),
                    windowNode("7", "8", "5", "20f"),
                    filterCountLessThan("8", "9", "7", "3"),
                    aggrNode("9", "2", "8", "distinct")
                ]
            },

            // --- Task 3: Player Motion Ratio ---

            {
                "title": "Motion Category (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_motion_category", "8"),
                    decodeNode("5", "1"),
                    llmNode("5", PROMPTS.vbMotionCategory, "7", "3"),
                    windowNode("7", "8", "5", "20f"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Players Moving (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_players_moving", "8"),
                    decodeNode("5", "1"),
                    llmNode("5", PROMPTS.vbMoving, "7", "3"),
                    windowNode("7", "8", "5", "20f"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Players Standing (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_players_standing", "8"),
                    decodeNode("5", "1"),
                    llmNode("5", PROMPTS.vbStanding, "7", "3"),
                    windowNode("7", "8", "5", "20f"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Players Jumping (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_players_jumping", "8"),
                    decodeNode("5", "1"),
                    llmNode("5", PROMPTS.vbJumping, "7", "3"),
                    windowNode("7", "8", "5", "20f"),
                    aggrNode("8", "2", "7")
                ]
            },

            // --- Task 4: Action Counts / Top-K ---

            {
                "title": "Top Actions (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_top_actions", "8"),
                    decodeNode("5", "1"),
                    llmNode("5", PROMPTS.vbActionGeneric, "7", "3"),
                    windowNode("7", "8", "5", "20f"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Spike Count (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_spike_count", "8"),
                    decodeNode("5", "1"),
                    llmNode("5", PROMPTS.vbSpiking, "7", "3"),
                    windowNode("7", "8", "5", "20f"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Set Count (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_set_count", "8"),
                    decodeNode("5", "1"),
                    llmNode("5", PROMPTS.vbSetting, "7", "3"),
                    windowNode("7", "8", "5", "20f"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Block Count (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_block_count", "8"),
                    decodeNode("5", "1"),
                    llmNode("5", PROMPTS.vbBlocking, "7", "3"),
                    windowNode("7", "8", "5", "20f"),
                    aggrNode("8", "2", "7")
                ]
            },

            // --- Task 5: Action Sequence Detection ---

            {
                "title": "Set→Spike Events (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_set_spike", "8"),
                    decodeNode("5", "1"),
                    llmNode("5", PROMPTS.vbSetSpike, "7", "3"),
                    windowNode("7", "8", "5", "20f"),
                    aggrNode("8", "2", "7", "ordered_set_spike")
                ]
            },

            {
                "title": "Set→Block Events (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_set_block", "8"),
                    decodeNode("5", "1"),
                    llmNode("5", PROMPTS.vbSetBlock, "7", "3"),
                    windowNode("7", "8", "5", "20f"),
                    aggrNode("8", "2", "7", "ordered_set_block")
                ]
            },

            {
                "title": "Dig→Set Events (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_dig_set", "8"),
                    decodeNode("5", "1"),
                    llmNode("5", PROMPTS.vbDigSet, "7", "3"),
                    windowNode("7", "8", "5", "20f"),
                    aggrNode("8", "2", "7", "ordered_dig_set")
                ]
            },

            {
                "title": "Jump→Spike Events (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_jump_spike", "8"),
                    decodeNode("5", "1"),
                    llmNode("5", PROMPTS.vbJumpSpike, "7", "3"),
                    windowNode("7", "8", "5", "20f"),
                    aggrNode("8", "2", "7", "ordered_jump_spike")
                ]
            },

            // --- Task 6: Player Position Tracking ---

            {
                "title": "Spike Bounding Boxes (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_bbox_spike", "8"),
                    decodeNode("4", "1"),
                    frameBatcherNode("4", "4", "5", "3"),
                    llmNode("5", PROMPTS.vbBboxSpike, "7", "4"),
                    windowNode("7", "8", "5", "20f"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Block Bounding Boxes (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_bbox_block", "8"),
                    decodeNode("4", "1"),
                    frameBatcherNode("4", "4", "5", "3"),
                    llmNode("5", PROMPTS.vbBboxBlock, "7", "4"),
                    windowNode("7", "8", "5", "20f"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Set Bounding Boxes (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_bbox_set", "8"),
                    decodeNode("4", "1"),
                    frameBatcherNode("4", "4", "5", "3"),
                    llmNode("5", PROMPTS.vbBboxSet, "7", "4"),
                    windowNode("7", "8", "5", "20f"),
                    aggrNode("8", "2", "7")
                ]
            },

            {
                "title": "Dig Bounding Boxes (Window)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("volleyball_bbox_dig", "8"),
                    decodeNode("4", "1"),
                    frameBatcherNode("4", "4", "5", "3"),
                    llmNode("5", PROMPTS.vbBboxDig, "7", "4"),
                    windowNode("7", "8", "5", "20f"),
                    aggrNode("8", "2", "7")
                ]
            },

        ]
    },

    // ==================== BLOCK 4: Case-specific composite optimizations ====================
    {
        dataset: "Cars (Case-Specific Composite)",
        runnable: true,
        senderScript: "running/Topics/Cars/Data/send_video.py",
        queries: [

            // Brand identification: detail matters, color does not.
            {
                "title": "Case Car Brand Generic (R854)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_brand_generic_r854", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.brandGeneric, "2", "4")
                ]
            },

            {
                "title": "Case Car Brand Ford (R854)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_brand_ford_r854", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.brandFord, "2", "4")
                ]
            },

            {
                "title": "Case Car Brand Renault (R854)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_brand_renault_r854", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.brandRenault, "2", "4")
                ]
            },

            {
                "title": "Case Car Brand Toyota (R854)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_brand_toyota_r854", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.brandToyota, "2", "4")
                ]
            },

            // Generic color: do not pre-filter by one color, because any color can be the answer.
            {
                "title": "Case Car Color Generic (R480)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_color_generic_r480", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.colorGeneric, "2", "4")
                ]
            },

            // Specific color queries: matching CV filter first, then small image for the LLM.
            {
                "title": "Case Car Color Red (CFred+R480)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_color_red_cfred_r480", "6"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_red", "5", "3", "2"),
                    resizeNode("5", "6", "4", "480", "270"),
                    llmNode("6", PROMPTS.colorRed, "2", "5")
                ]
            },

            {
                "title": "Case Car Color Grey (CFgrey+R480)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_color_grey_cfgrey_r480", "6"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_grey", "5", "3", "2"),
                    resizeNode("5", "6", "4", "480", "270"),
                    llmNode("6", PROMPTS.colorGrey, "2", "5")
                ]
            },

            {
                "title": "Case Car Color White (CFwhite+R480)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_color_white_cfwhite_r480", "6"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_white", "5", "3", "2"),
                    resizeNode("5", "6", "4", "480", "270"),
                    llmNode("6", PROMPTS.colorWhite, "2", "5")
                ]
            },

            {
                "title": "Case Car Color Blue (CFblue+R480)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_color_blue_cfblue_r480", "6"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_blue", "5", "3", "2"),
                    resizeNode("5", "6", "4", "480", "270"),
                    llmNode("6", PROMPTS.colorBlue, "2", "5")
                ]
            },

            // License plate recognition: native resolution, only a conservative white/red pre-filter.
            {
                "title": "Case License Plate Recognition (CFwhite native)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_plate_cfwhite_native", "5"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_white", "5", "3", "2"),
                    llmNode("5", PROMPTS.plateGeneric, "2", "4")
                ]
            },

            {
                "title": "Case Specific Plate QRF8G17 (CFwhite native)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_qrf8g17_cfwhite_native", "5"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_white", "5", "3", "2"),
                    llmNode("5", PROMPTS.plateSpecific, "2", "4")
                ]
            },

            {
                "title": "Case Color+Plate Red (CFred native)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_color_plate_red_cfred_native", "5"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_red", "5", "3", "2"),
                    llmNode("5", PROMPTS.colorPlateRed, "2", "4")
                ]
            },

            // Windowed cars: preserve the limiting detail before aggregation.
            {
                "title": "Case Most Popular Brand (R854)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_most_popular_brand_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.mostPopularBrand, "7", "4"),
                    windowNode("7", "9", "5"),
                    aggrNode("9", "2", "7")
                ]
            },

            {
                "title": "Case Most Popular Color (R480)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_most_popular_color_r480", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.colorGeneric, "7", "4"),
                    windowNode("7", "9", "5"),
                    aggrNode("9", "2", "7")
                ]
            },

            {
                "title": "Case Most Popular Brand+Color (R854)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_most_popular_brand_color_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.mostPopularBrandColor, "7", "4"),
                    windowNode("7", "9", "5"),
                    aggrNode("9", "2", "7")
                ]
            },

            {
                "title": "Case Most Popular Color Ford (R854)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_most_popular_color_ford_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.mostPopularColorFord, "7", "4"),
                    windowNode("7", "9", "5"),
                    aggrNode("9", "2", "7")
                ]
            },

            {
                "title": "Case Most Popular Brand Red (CFred+R854)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_most_popular_brand_red_cfred_r854", "10"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_red", "5", "3", "2"),
                    resizeNode("5", "6", "4", "854", "480"),
                    llmNode("6", PROMPTS.mostPopularBrandRed, "8", "5"),
                    windowNode("8", "10", "6"),
                    aggrNode("10", "2", "8")
                ]
            },

            {
                "title": "Case Unique Plates (CFwhite native)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_unique_plates_cfwhite_native", "9"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_white", "5", "3", "2"),
                    llmNode("5", PROMPTS.plateGeneric, "7", "4"),
                    windowNode("7", "9", "5"),
                    aggrNode("9", "2", "7")
                ]
            },

            {
                "title": "Case Repeating Plates (CFwhite native)",
                "nodes": [
                    carsSource("3"),
                    carsSink("case_cars_repeating_plates_cfwhite_native", "10"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_white", "5", "3", "2"),
                    llmNode("5", PROMPTS.plateGeneric, "7", "4"),
                    windowNode("7", "8", "5"),
                    filterCountLessThan("8", "10", "7", "3"),
                    aggrNode("10", "2", "8", "distinct")
                ]
            },
        ]
    },

    {
        dataset: "Volleyball (Case-Specific Composite)",
        runnable: true,
        senderScript: "running/Topics/Volleyball/Data/send_volleyball.py",
        queries: [

            // Pose/action recognition: medium-high resolution, no color filter.
            {
                "title": "Case Repeated Spikers (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_repeated_spikers_r854", "10"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbSpiking, "7", "4"),
                    windowNode("7", "8", "5", "20f"),
                    filterCountLessThan("8", "10", "7", "3"),
                    aggrNode("10", "2", "8", "distinct")
                ]
            },

            {
                "title": "Case Repeated Setters (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_repeated_setters_r854", "10"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbSetting, "7", "4"),
                    windowNode("7", "8", "5", "20f"),
                    filterCountLessThan("8", "10", "7", "3"),
                    aggrNode("10", "2", "8", "distinct")
                ]
            },

            {
                "title": "Case Repeated Blockers (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_repeated_blockers_r854", "10"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbBlocking, "7", "4"),
                    windowNode("7", "8", "5", "20f"),
                    filterCountLessThan("8", "10", "7", "3"),
                    aggrNode("10", "2", "8", "distinct")
                ]
            },

            {
                "title": "Case Repeated Diggers (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_repeated_diggers_r854", "10"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbDigging, "7", "4"),
                    windowNode("7", "8", "5", "20f"),
                    filterCountLessThan("8", "10", "7", "3"),
                    aggrNode("10", "2", "8", "distinct")
                ]
            },

            // Grayscale A/B variants for action recognition only.
            {
                "title": "Case Repeated Spikers (G+R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_repeated_spikers_g_r854", "11"),
                    decodeNode("4", "1"),
                    grayscaleNode("4", "5", "3"),
                    resizeNode("5", "6", "4", "854", "480"),
                    llmNode("6", PROMPTS.vbSpiking, "8", "5"),
                    windowNode("8", "9", "6", "20f"),
                    filterCountLessThan("9", "11", "8", "3"),
                    aggrNode("11", "2", "9", "distinct")
                ]
            },

            {
                "title": "Case Repeated Setters (G+R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_repeated_setters_g_r854", "11"),
                    decodeNode("4", "1"),
                    grayscaleNode("4", "5", "3"),
                    resizeNode("5", "6", "4", "854", "480"),
                    llmNode("6", PROMPTS.vbSetting, "8", "5"),
                    windowNode("8", "9", "6", "20f"),
                    filterCountLessThan("9", "11", "8", "3"),
                    aggrNode("11", "2", "9", "distinct")
                ]
            },

            {
                "title": "Case Repeated Blockers (G+R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_repeated_blockers_g_r854", "11"),
                    decodeNode("4", "1"),
                    grayscaleNode("4", "5", "3"),
                    resizeNode("5", "6", "4", "854", "480"),
                    llmNode("6", PROMPTS.vbBlocking, "8", "5"),
                    windowNode("8", "9", "6", "20f"),
                    filterCountLessThan("9", "11", "8", "3"),
                    aggrNode("11", "2", "9", "distinct")
                ]
            },

            {
                "title": "Case Repeated Diggers (G+R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_repeated_diggers_g_r854", "11"),
                    decodeNode("4", "1"),
                    grayscaleNode("4", "5", "3"),
                    resizeNode("5", "6", "4", "854", "480"),
                    llmNode("6", PROMPTS.vbDigging, "8", "5"),
                    windowNode("8", "9", "6", "20f"),
                    filterCountLessThan("9", "11", "8", "3"),
                    aggrNode("11", "2", "9", "distinct")
                ]
            },

            // Coarse motion: small image is enough.
            {
                "title": "Case Motion Category (R480)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_motion_category_r480", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.vbMotionCategory, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7")
                ]
            },

            {
                "title": "Case Players Moving (R480)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_players_moving_r480", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.vbMoving, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7")
                ]
            },

            {
                "title": "Case Players Standing (R480)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_players_standing_r480", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.vbStanding, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7")
                ]
            },

            {
                "title": "Case Players Jumping Diagnostic (R480)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_players_jumping_diag_r480", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.vbJumping, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7")
                ]
            },

            // Counts and top actions: action detail, no aggressive skipping.
            {
                "title": "Case Top Actions (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_top_actions_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbActionGeneric, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7")
                ]
            },

            {
                "title": "Case Top Actions (G+R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_top_actions_g_r854", "10"),
                    decodeNode("4", "1"),
                    grayscaleNode("4", "5", "3"),
                    resizeNode("5", "6", "4", "854", "480"),
                    llmNode("6", PROMPTS.vbActionGeneric, "8", "5"),
                    windowNode("8", "10", "6", "20f"),
                    aggrNode("10", "2", "8")
                ]
            },

            {
                "title": "Case Spike Count (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_spike_count_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbSpiking, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7")
                ]
            },

            {
                "title": "Case Set Count (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_set_count_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbSetting, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7")
                ]
            },

            {
                "title": "Case Block Count (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_block_count_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbBlocking, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7")
                ]
            },

            {
                "title": "Case Spike Count Precision (R854+F8)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_spike_count_r854_f8", "10"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbSpiking, "7", "4"),
                    windowNode("7", "8", "5", "20f"),
                    filterCountLessThan("8", "10", "7", "8"),
                    aggrNode("10", "2", "8")
                ]
            },

            {
                "title": "Case Block Count Precision (R854+F8)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_block_count_r854_f8", "10"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbBlocking, "7", "4"),
                    windowNode("7", "8", "5", "20f"),
                    filterCountLessThan("8", "10", "7", "8"),
                    aggrNode("10", "2", "8")
                ]
            },

            {
                "title": "Case Players Moving Precision (R480+F8)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_players_moving_r480_f8", "10"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.vbMoving, "7", "4"),
                    windowNode("7", "8", "5", "20f"),
                    filterCountLessThan("8", "10", "7", "8"),
                    aggrNode("10", "2", "8")
                ]
            },

            // Ordered pairs: preserve sequence by avoiding skip-frame recipes.
            {
                "title": "Case Set->Spike Events (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_set_spike_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbSetSpike, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7", "ordered_set_spike")
                ]
            },

            {
                "title": "Case Set->Block Events (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_set_block_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbSetBlock, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7", "ordered_set_block")
                ]
            },

            {
                "title": "Case Dig->Set Events (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_dig_set_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbDigSet, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7", "ordered_dig_set")
                ]
            },

            {
                "title": "Case Jump->Spike Diagnostic (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_jump_spike_diag_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbJumpSpike, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7", "ordered_jump_spike")
                ]
            },

            // BBox/localization: high resolution plus small temporal batches.
            {
                "title": "Case Spike Bbox (R960+B3)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_bbox_spike_r960_b3", "10"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "960", "540"),
                    frameBatcherNode("5", "3", "6", "4"),
                    llmNode("6", PROMPTS.vbBboxSpike, "8", "5"),
                    windowNode("8", "10", "6", "20f"),
                    aggrNode("10", "2", "8")
                ]
            },

            {
                "title": "Case Block Bbox (R960+B3)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_bbox_block_r960_b3", "10"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "960", "540"),
                    frameBatcherNode("5", "3", "6", "4"),
                    llmNode("6", PROMPTS.vbBboxBlock, "8", "5"),
                    windowNode("8", "10", "6", "20f"),
                    aggrNode("10", "2", "8")
                ]
            },

            {
                "title": "Case Set Bbox Diagnostic (R960+B3)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_bbox_set_diag_r960_b3", "10"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "960", "540"),
                    frameBatcherNode("5", "3", "6", "4"),
                    llmNode("6", PROMPTS.vbBboxSet, "8", "5"),
                    windowNode("8", "10", "6", "20f"),
                    aggrNode("10", "2", "8")
                ]
            },

            {
                "title": "Case Dig Bbox (R960+B3)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("case_vb_bbox_dig_r960_b3", "10"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "960", "540"),
                    frameBatcherNode("5", "3", "6", "4"),
                    llmNode("6", PROMPTS.vbBboxDig, "8", "5"),
                    windowNode("8", "10", "6", "20f"),
                    aggrNode("10", "2", "8")
                ]
            },
        ]
    },

    // ==================== BLOCK 5: Final Optimized Queries ====================
    {
        dataset: "Cars (Optimized Final)",
        runnable: true,
        senderScript: "running/Topics/Cars/Data/send_video.py",
        queries: [

            bestOptimizedQuery({
                "title": "Optimized Car Brand Generic (R854)",
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_brand_generic_r854", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.brandGeneric, "2", "4")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Car Brand Ford (R854)",
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_brand_ford_r854", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.brandFord, "2", "4")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Car Brand Renault (R854)",
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_brand_renault_r854", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.brandRenault, "2", "4")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Car Brand Toyota (R854)",
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_brand_toyota_r854", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.brandToyota, "2", "4")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Car Color Generic (R480)",
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_color_generic_r480", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.colorGeneric, "2", "4")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Car Color Red (CFred+R480)",
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_color_red_cfred_r480", "6"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_red", "5", "3", "2"),
                    resizeNode("5", "6", "4", "480", "270"),
                    llmNode("6", PROMPTS.colorRed, "2", "5")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Car Color Grey (CFgrey+R480)",
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_color_grey_cfgrey_r480", "6"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_grey", "5", "3", "2"),
                    resizeNode("5", "6", "4", "480", "270"),
                    llmNode("6", PROMPTS.colorGrey, "2", "5")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Car Color White (CFwhite+R480)",
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_color_white_cfwhite_r480", "6"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_white", "5", "3", "2"),
                    resizeNode("5", "6", "4", "480", "270"),
                    llmNode("6", PROMPTS.colorWhite, "2", "5")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Car Color Blue (CFblue+R480)",
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_color_blue_cfblue_r480", "6"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_blue", "5", "3", "2"),
                    resizeNode("5", "6", "4", "480", "270"),
                    llmNode("6", PROMPTS.colorBlue, "2", "5")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized License Plate Recognition (R1120)",
                "meta": { "highlightRed": true },
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_plate_r1120", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "1120", "630"),
                    llmNode("5", PROMPTS.plateGeneric, "2", "4")
                ]
            }, true),

            {
                "title": "Ablation License Plate Recognition (CFwhite native)",
                "meta": { "changedThisTurn": true },
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_plate_cfwhite_native", "5"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_white", "5", "3", "2"),
                    llmNode("5", PROMPTS.plateGeneric, "2", "4")
                ]
            },

            bestOptimizedQuery({
                "title": "Optimized Specific Plate QRF8G17 (R1120)",
                "meta": { "highlightRed": true },
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_qrf8g17_r1120", "5"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "1120", "630"),
                    llmNode("5", PROMPTS.plateSpecific, "2", "4")
                ]
            }, true),

            bestOptimizedQuery({
                "title": "Optimized Color+Plate Red (CFred+R1120)",
                "meta": { "highlightRed": true },
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_color_plate_red_cfred_r1120", "6"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_red", "5", "3", "2"),
                    resizeNode("5", "6", "4", "1120", "630"),
                    llmNode("6", PROMPTS.colorPlateRed, "2", "5")
                ]
            }, true),

            bestOptimizedQuery({
                "title": "Optimized Red Plate Lookup (CFred+R1120+S3)",
                "meta": { "highlightRed": true },
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_red_plate_cfred_r1120_s3", "7"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_red", "5", "3", "2"),
                    resizeNode("5", "6", "4", "1120", "630"),
                    skipFramesNode("6", "3", "0", "7", "5"),
                    llmNode("7", PROMPTS.colorPlateRed, "2", "6")
                ]
            }, true),

            bestOptimizedQuery({
                "title": "Optimized Most Popular Brand (R854)",
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_most_popular_brand_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.mostPopularBrand, "7", "4"),
                    windowNode("7", "9", "5"),
                    aggrNode("9", "2", "7")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Most Popular Color (R480)",
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_most_popular_color_r480", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.colorGeneric, "7", "4"),
                    windowNode("7", "9", "5"),
                    aggrNode("9", "2", "7")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Most Popular Color (Skip 10)",
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_most_popular_color_skip10", "9"),
                    decodeNode("4", "1"),
                    skipFramesNode("4", "10", "0", "5", "3"),
                    llmNode("5", PROMPTS.colorGeneric, "7", "4"),
                    windowNode("7", "9", "5"),
                    aggrNode("9", "2", "7")
                ]
            }, true),

            bestOptimizedQuery({
                "title": "Optimized Most Popular Brand+Color (R854)",
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_most_popular_brand_color_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.mostPopularBrandColor, "7", "4"),
                    windowNode("7", "9", "5"),
                    aggrNode("9", "2", "7")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Most Popular Color Ford (R854)",
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_most_popular_color_ford_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.mostPopularColorFord, "7", "4"),
                    windowNode("7", "9", "5"),
                    aggrNode("9", "2", "7")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Most Popular Brand Red (CFred+R854)",
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_most_popular_brand_red_cfred_r854", "10"),
                    decodeNode("4", "1"),
                    cvColorFilterNode("4", "cv_color_red", "5", "3", "2"),
                    resizeNode("5", "6", "4", "854", "480"),
                    llmNode("6", PROMPTS.mostPopularBrandRed, "8", "5"),
                    windowNode("8", "10", "6"),
                    aggrNode("10", "2", "8")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Unique Plates (R1120)",
                "meta": { "highlightRed": true },
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_unique_plates_r1120", "8"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "1120", "630"),
                    llmNode("5", PROMPTS.plateGeneric, "7", "4"),
                    windowNode("7", "8", "5"),
                    aggrNode("8", "2", "7")
                ]
            }, true),

            bestOptimizedQuery({
                "title": "Optimized Repeating Plates (R1120)",
                "meta": { "highlightRed": true },
                "nodes": [
                    carsSource("3"),
                    carsSink("opt_cars_repeating_plates_r1120", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "1120", "630"),
                    llmNode("5", PROMPTS.plateGeneric, "7", "4"),
                    windowNode("7", "8", "5"),
                    filterCountLessThan("8", "9", "7", "3"),
                    aggrNode("9", "2", "8", "distinct")
                ]
            }, true),
        ]
    },

    {
        dataset: "Volleyball (Optimized Final)",
        runnable: true,
        senderScript: "running/Topics/Volleyball/Data/send_volleyball.py",
        queries: [

            bestOptimizedQuery({
                "title": "Optimized Repeated Spikers (G+R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_repeated_spikers_g_r854", "11"),
                    decodeNode("4", "1"),
                    grayscaleNode("4", "5", "3"),
                    resizeNode("5", "6", "4", "854", "480"),
                    llmNode("6", PROMPTS.vbSpiking, "8", "5"),
                    windowNode("8", "9", "6", "20f"),
                    filterCountLessThan("9", "11", "8", "3"),
                    aggrNode("11", "2", "9", "distinct")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Repeated Setters (G+R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_repeated_setters_g_r854", "11"),
                    decodeNode("4", "1"),
                    grayscaleNode("4", "5", "3"),
                    resizeNode("5", "6", "4", "854", "480"),
                    llmNode("6", PROMPTS.vbSetting, "8", "5"),
                    windowNode("8", "9", "6", "20f"),
                    filterCountLessThan("9", "11", "8", "3"),
                    aggrNode("11", "2", "9", "distinct")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Repeated Blockers (G+R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_repeated_blockers_g_r854", "11"),
                    decodeNode("4", "1"),
                    grayscaleNode("4", "5", "3"),
                    resizeNode("5", "6", "4", "854", "480"),
                    llmNode("6", PROMPTS.vbBlocking, "8", "5"),
                    windowNode("8", "9", "6", "20f"),
                    filterCountLessThan("9", "11", "8", "3"),
                    aggrNode("11", "2", "9", "distinct")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Repeated Diggers (G+R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_repeated_diggers_g_r854", "11"),
                    decodeNode("4", "1"),
                    grayscaleNode("4", "5", "3"),
                    resizeNode("5", "6", "4", "854", "480"),
                    llmNode("6", PROMPTS.vbDigging, "8", "5"),
                    windowNode("8", "9", "6", "20f"),
                    filterCountLessThan("9", "11", "8", "3"),
                    aggrNode("11", "2", "9", "distinct")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Motion Category (R480)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_motion_category_r480", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.vbMotionCategory, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Players Moving (R480)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_players_moving_r480", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.vbMoving, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Players Standing (R480)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_players_standing_r480", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.vbStanding, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Players Jumping (R480)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_players_jumping_r480", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "480", "270"),
                    llmNode("5", PROMPTS.vbJumping, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Top Actions (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_top_actions_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbActionGeneric, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Spike Count (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_spike_count_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbSpiking, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Set Count (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_set_count_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbSetting, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Block Count (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_block_count_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbBlocking, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Set->Spike Events (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_set_spike_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbSetSpike, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7", "ordered_set_spike")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Set->Block Events (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_set_block_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbSetBlock, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7", "ordered_set_block")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Dig->Set Events (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_dig_set_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbDigSet, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7", "ordered_dig_set")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Jump->Spike Events (R854)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_jump_spike_r854", "9"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "854", "480"),
                    llmNode("5", PROMPTS.vbJumpSpike, "7", "4"),
                    windowNode("7", "9", "5", "20f"),
                    aggrNode("9", "2", "7", "ordered_jump_spike")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Spike Bounding Boxes (R960+B3+W20)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_bbox_spike_r960_b3_w20", "10"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "960", "540"),
                    frameBatcherNode("5", "3", "6", "4"),
                    llmNode("6", PROMPTS.vbBboxSpike, "8", "5"),
                    windowNode("8", "10", "6", "20f"),
                    aggrNode("10", "2", "8")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Block Bounding Boxes (R960+B3+W20)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_bbox_block_r960_b3_w20", "10"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "960", "540"),
                    frameBatcherNode("5", "3", "6", "4"),
                    llmNode("6", PROMPTS.vbBboxBlock, "8", "5"),
                    windowNode("8", "10", "6", "20f"),
                    aggrNode("10", "2", "8")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Set Bounding Boxes (R960+B3+W20)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_bbox_set_r960_b3_w20", "10"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "960", "540"),
                    frameBatcherNode("5", "3", "6", "4"),
                    llmNode("6", PROMPTS.vbBboxSet, "8", "5"),
                    windowNode("8", "10", "6", "20f"),
                    aggrNode("10", "2", "8")
                ]
            }),

            bestOptimizedQuery({
                "title": "Optimized Dig Bounding Boxes (R960+B3+W20)",
                "nodes": [
                    volleyballSource("3"),
                    carsSink("opt_vb_bbox_dig_r960_b3_w20", "10"),
                    decodeNode("4", "1"),
                    resizeNode("4", "5", "3", "960", "540"),
                    frameBatcherNode("5", "3", "6", "4"),
                    llmNode("6", PROMPTS.vbBboxDig, "8", "5"),
                    windowNode("8", "10", "6", "20f"),
                    aggrNode("10", "2", "8")
                ]
            }),
        ]
    }
];

// Backward-compatible flat export
export const queries = queryGroups.flatMap(g => g.queries);

