
// src/directPythonExport.js

import {
    generateImports,
    generateMapDecodeStreamClass,
    generateMapResizeImageClass,
    generateMapPromptLLMClass,
    generateMapRecolorImageClass,
    generateFilterNotEmptyClass,
    generateFilterNotSkippedClass,
    generateMapGetCountsMethod,
    generateMapDetectOrderedPairMethod,
    generateReduceWindowResultsClass,
    generateMapRemoveLowCountMethod,
    generateMapChangeFormatClass,
    generateGlobalConstants,
    generateMapCVColorFilterClass,
    generateMapComputeMetricsClass,
    generateMapSkipFramesClass,
    generateMapFrameBatcherClass,
} from './Methodtemplates.js';
import { getNodeParameters } from "./utils/export-utils.js";
import { nodeTypes } from "../../components/nodes/defaultNodes.js";

const ORDERED_PAIR_AGGR = {
    ordered_set_spike: { first: 'set', second: 'spike', label: 'set->spike' },
    ordered_set_block: { first: 'set', second: 'block', label: 'set->block' },
    ordered_dig_set: { first: 'dig', second: 'set', label: 'dig->set' },
    ordered_jump_spike: { first: 'jump', second: 'spike', label: 'jump->spike' },
};

function getOrderedPairAggrConfig(node) {
    if (!node || typeof node !== 'object') return null;
    const subtype = node.subtype || node.params?.subtype;
    return ORDERED_PAIR_AGGR[subtype] || null;
}

/**
 * @param {Array} nodes
 * @param {Array} edges
 * @param {string} projectName
 * @param {object} paramOverrides - Optional parameter overrides keyed by node ID
 * @param {Array} customNodes - Array of custom node definitions
 * @returns {string}
 */
export function generateDirectPython(nodes, edges, projectName = "FlinkPipeline", customNodes = []) {
    const startNode = nodes.find(n => n.data?.label === 'Kafka Sink 1' || n.type === 'start');
    const endNode = nodes.find(n => n.data?.label === 'Kafka Sink 2' || n.type === 'end');
    if (!startNode || !endNode) {
        throw new Error('Pipeline needs both start and end');
    }

    const ordered = getOrderedNodes(nodes, edges)
        .filter(n => !['start', 'end'].includes(n.type) && !['Kafka Sink 1', 'Kafka Sink 2'].includes(n.data?.label));

    const used = new Set();
    let classes = [];

    // 1. headers + constants
    classes.push(generateImports());
    //classes.push(generateGlobalConstants());

    // 2. per-node class defs
    ordered.forEach(n => {
        const type = (n.data?.label || '').toLowerCase();
        const p = getNodeParameters(n);

        // Check if this is a custom node
        const customNode = customNodes.find(cn => cn.label.toLowerCase() === type);
        if (customNode && !used.has(customNode.label)) {
            // Add the custom Python class code
            classes.push(customNode.pythonClass);
            used.add(customNode.label);
            return; // Skip default node handling
        }

        if ((type === 'decode') && !used.has('MapDecodeStream')) {
            classes.push(generateMapDecodeStreamClass()); used.add('MapDecodeStream');
        }
        if ((type === 'resize') && !used.has('MapResizeImage')) {
            // const width = (p.width && p.width.toString().trim()) ? p.width : "640";
            // const height = (p.height && p.height.toString().trim()) ? p.height : "360";

            classes.push(generateMapResizeImageClass()); used.add('MapResizeImage');
        }
        if ((type === 'llm') && !used.has('MapPromptLLM')) {
            //const userPrompt = (p.prompt && p.prompt.trim()) ? p.prompt : "Default Prompt: Describe what is in this image.";

            classes.push(generateMapPromptLLMClass()); used.add('MapPromptLLM');
        }
        if ((type === 'cv color filter') && !used.has('MapCVColorFilter')) {
            classes.push(generateMapCVColorFilterClass()); used.add('MapCVColorFilter');
        }
        if ((type === 'skip frames') && !used.has('MapSkipFrames')) {
            classes.push(generateMapSkipFramesClass()); used.add('MapSkipFrames');
        }
        if ((type === 'frame batcher') && !used.has('MapFrameBatcher')) {
            classes.push(generateMapFrameBatcherClass()); used.add('MapFrameBatcher');
        }
        if ((type === 'grayscale') && !used.has('MapRecolorImage')) {
            classes.push(generateMapRecolorImageClass()); used.add('MapRecolorImage');




        }
        if ((type === 'filter') && p.subtype === 'remove_empty_values' && !used.has('FilterNotEmpty')) {
            classes.push(generateFilterNotEmptyClass()); used.add('FilterNotEmpty');
        }
        if ((type === 'filter') && p.subtype === 'remove_skipped' && !used.has('FilterNotSkipped')) {
            classes.push(generateFilterNotSkippedClass()); used.add('FilterNotSkipped');
        }
        if ((type === 'filter') && p.subtype === 'remove_count_less_than' && !used.has('generateMapRemoveLowCountMethod')) {
            // ensure we have MapGetCounts and MapRemoveLowCount when using the remove_count_less_than filter
            if (!used.has('MapGetCounts')) { classes.push(generateMapGetCountsMethod()); used.add('MapGetCounts'); }
            classes.push(generateMapRemoveLowCountMethod()); used.add('generateMapRemoveLowCountMethod');
        }









        if (type === 'aggr') {
            const orderedPairCfg = getOrderedPairAggrConfig(n);
            if (orderedPairCfg && !used.has('MapDetectOrderedPair')) {
                classes.push(generateMapDetectOrderedPairMethod()); used.add('MapDetectOrderedPair');
            }
            if (!orderedPairCfg && !used.has('MapGetCounts')) {
                classes.push(generateMapGetCountsMethod()); used.add('MapGetCounts');
            }
        }
        if ((type === 'window') && !used.has('ReduceWindowResults')) {
            classes.push(generateReduceWindowResultsClass()); used.add('ReduceWindowResults');
        }
        if ((type === 'window') && !used.has('MapChangeFormat')) {
            classes.push(generateMapChangeFormatClass()); used.add('MapChangeFormat');
        }

    });

    // Always add metrics computation class before the sink
    classes.push(generateMapComputeMetricsClass());

    // 3. main pipeline
    classes.push(generateMainPipeline(startNode, endNode, ordered, projectName, customNodes));

    return classes.join('\n\n');
}


function generateMainPipeline(startNode, endNode, nodes, projectName, customNodes = []) {

    const startParameters = getNodeParameters(startNode);

    // 2. Use those parameters in your pipeline code
    const server_in = startParameters.server || 'No_Server_given_in';
    const group_Id_in = startParameters.group_id || 'No_Group_Given_in';
    const topic_in = startParameters.topic || 'No_Topic_Given_in';
    const outT = `${projectName.toLowerCase().replace(/\s+/g, '_')}_out`;

    let code = `
env = StreamExecutionEnvironment.get_execution_environment()

kafka_source = KafkaSource.builder()\\
  .set_bootstrap_servers("${server_in}")\\
  .set_group_id("${group_Id_in}")\\
  .set_topics("${topic_in}")\\
  .set_starting_offsets(KafkaOffsetsInitializer.earliest())\\
  .set_value_only_deserializer(SimpleStringSchema())\\
  .build()

watermark_strategy = WatermarkStrategy.for_bounded_out_of_orderness(Duration.of_seconds(0))\\
  .with_timestamp_assigner(lambda e,_: ujson.loads(e)["timestamp"])

stream = env.from_source(kafka_source, watermark_strategy, "Kafka Source")
`;

    let current = 'stream';
    nodes.forEach((n, i) => {
        const t = (n.data?.label || '').toLowerCase();
        const next = `stream_${i + 1}`;
        let op = '';
        if (t === 'decode') op = `.map(MapDecodeStream())`;
        if (t === 'resize') {
            const params = getNodeParameters(n);
            const width = params.width || '640';
            const height = params.height || '360';
            op = `.map(MapResizeImage(${width},${height}))`;
        }
        if (t === 'llm') {

            const prompti = getNodeParameters(n);
            const prompt_F = prompti.prompt || 'Default Prompt: Describe what is in this image.';
            const model = prompti.subtype || 'llava';
            op = `.map(MapPromptLLM("""${prompt_F}""", """${model}"""))`;
        }
        if (t === 'grayscale') op = `.map(MapRecolorImage())`;
        if (t === 'cv color filter') {
            const cvParams = getNodeParameters(n);
            const colorKey = cvParams.subtype || 'cv_color_red';
            const threshold = cvParams.threshold || '5';
            op = `.map(MapCVColorFilter("${colorKey}", ${threshold}))`;
        }
        if (t === 'skip frames') {
            const skipParams = getNodeParameters(n);
            const skipOnEmpty = skipParams.skip_on_empty || '0';
            const skipOnDetect = skipParams.skip_on_detect || '0';
            op = `.map(MapSkipFrames(${skipOnEmpty}, ${skipOnDetect}))`;
        }
        if (t === 'frame batcher') {
            const batchParams = getNodeParameters(n);
            const batchSize = batchParams.batch_size || '5';
            op = `.map(MapFrameBatcher(${batchSize}))`;
        }

        if (t === 'filter') {


            switch (getNodeParameters(n).subtype) {
                case 'remove_empty_values':
                    op = `.filter(FilterNotEmpty())`;
                    break;
                case 'remove_skipped':
                    op = `.filter(FilterNotSkipped())`;
                    break;
                case 'remove_count_less_than':
                    // Read threshold parameter (M) from node params; default to 3
                    const filterParams = getNodeParameters(n);
                    const threshold = (filterParams && filterParams['Remove Values Less Than']) ? filterParams['Remove Values Less Than'] : (filterParams && filterParams['remove_values_less_than']) ? filterParams['remove_values_less_than'] : 3;
                    op = `.map(MapGetCounts()).map(MapRemoveLowCount(${threshold}))`
                    break;
                default:
                    break;
            }



        }

        if (t === 'window') {
            const winParam = getNodeParameters(n);
            const rawWindowSize = (winParam.window_size !== undefined && winParam.window_size !== null)
                ? String(winParam.window_size).trim()
                : '';

            // Support explicit frame-count windows via "<N>f" (e.g. "20f").
            // Fallback remains processing-time seconds for backward compatibility.
            const frameMatch = rawWindowSize.match(/^(\d+)\s*f$/i);
            if (frameMatch) {
                const frameCount = Number(frameMatch[1]) || 10;
                // PyFlink in our runtime does not expose DataStream.count_window_all(...).
                // Use a single-key keyed count window to get equivalent tumbling frame windows.
                op = `.map(MapChangeFormat()).key_by(lambda _: 0, key_type=Types.INT()).count_window(${frameCount}).reduce(ReduceWindowResults())`;
            } else {
                const winParameter = rawWindowSize !== '' ? Number(rawWindowSize) : 10;
                op = `.map(MapChangeFormat()).window_all(TumblingProcessingTimeWindows.of(Time.seconds(${winParameter}))).reduce(ReduceWindowResults())`;
            }
        }

        if (t === 'aggr') {
            const orderedPairCfg = getOrderedPairAggrConfig(n);
            if (orderedPairCfg) {
                op = `.map(MapDetectOrderedPair("${orderedPairCfg.first}", "${orderedPairCfg.second}", "${orderedPairCfg.label}"))`;
            } else {
                op = `.map(MapGetCounts())`;
            }
        }

        // Check if this is a custom node
        const customNode = customNodes.find(cn => cn.label.toLowerCase() === t);
        if (customNode && !op) {
            // Get class name from Python class code (extract from "class ClassName:")
            const classNameMatch = customNode.pythonClass.match(/class\s+(\w+)/);
            const className = classNameMatch ? classNameMatch[1] : 'CustomNode';

            // Get parameters for this node
            const params = getNodeParameters(n);
            const paramValues = customNode.params
                ? customNode.params.map(p => {
                    const val = params[p.name];
                    // Handle string vs number parameters
                    if (p.type === 'number') {
                        return val || '0';
                    } else {
                        return `"""${val || ''}"""`;
                    }
                }).join(', ')
                : '';

            op = `.map(${className}().${customNode.method}(${paramValues}))`;
        }

        code += `\n# Procesing Node ${i + 1} (${t})`;
        code += `\n${next} = ${current}${op}`;
        current = next;
    });


    //Kafka Sink Out
    const endParameters = getNodeParameters(endNode);
    const server_out = endParameters.server || 'No_Server_Given_Out';
    const topic_out = endParameters.topic || 'No_Topic_Given_Out';

    // Add metrics computation before sink
    const metricsStream = `stream_metrics`;
    code += `\n\n# Compute metrics (accuracy, latency) before sending to sink`;
    code += `\n${metricsStream} = ${current}.map(MapComputeMetrics("${topic_out}"))`;


    code += `\n\nkafka_sink = KafkaSink.builder()\\
  .set_bootstrap_servers("${server_out}")\\
  .set_record_serializer(KafkaRecordSerializationSchema.builder()\\
       .set_topic("${topic_out}")\\
       .set_value_serialization_schema(SimpleStringSchema())\\
       .build())\\
  .build()

${metricsStream}.map(lambda x: ujson.dumps(x)).map(lambda x: x, Types.STRING()).sink_to(kafka_sink)

env.execute("${projectName}")
`;
    return code;
}


//––– helpers –––

function getOrderedNodes(nodes, edges) {
    if (!nodes.length) return [];
    const map = new Map(nodes.map(n => [n.id, n]));
    let start = nodes.find(n => n.data?.label === 'Kafka Sink 1' || n.type === 'start');
    if (!start) {
        const targets = new Set(edges.map(e => e.target));
        start = nodes.find(n => !targets.has(n.id)) || nodes[0];
    }
    const out = [], seen = new Set();
    let cur = start;
    while (cur && !seen.has(cur.id)) {
        out.push(cur); seen.add(cur.id);
        const e = edges.find(e => e.source === cur.id);
        cur = e ? map.get(e.target) : null;
    }
    return out;
}
