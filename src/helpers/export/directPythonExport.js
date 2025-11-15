
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
    generateReduceWindowResultsClass,
    generateMapRemoveLowCountMethod,
    generateMapChangeFormatClass,
    generateGlobalConstants,
} from './Methodtemplates.js';
import { getNodeParameters } from "./utils/export-utils.js";

/**
 * @param {Array} nodes
 * @param {Array} edges
 * @param {string} projectName
 * @returns {string}
 */
export function generateDirectPython(nodes, edges, projectName = "FlinkPipeline") {
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









        if ((type === 'window') && !used.has('ReduceWindowResults')) {
            classes.push(generateReduceWindowResultsClass()); used.add('ReduceWindowResults');
        }
        if ((type === 'window') && !used.has('MapChangeFormat')) {
            classes.push(generateMapChangeFormatClass()); used.add('MapChangeFormat');
        }

    });

    // include change‐format + reduce‐window
    // if (!used.has('MapChangeFormat')) classes.push(generateMapChangeFormatClass());
    // if (!used.has('ReduceWindowResults')) classes.push(generateReduceWindowResultsClass());

    // 3. main pipeline
    classes.push(generateMainPipeline(startNode, endNode, ordered, projectName));

    return classes.join('\n\n');
}


function generateMainPipeline(startNode, endNode, nodes, projectName) {

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
            const width_lbound = params.width_lbound || '320';
            const width_rbound = params.width_rbound || '640';
            const height_lbound = params.height_lbound || '180';
            const height_rbound = params.height_rbound || '360';

            // Validate that lower bounds are <= upper bounds
            if (Number(width_lbound) > Number(width_rbound)) {
                throw new Error(`Resize node ${n.id}: Width lower bound (${width_lbound}) cannot be greater than upper bound (${width_rbound})`);
            }
            if (Number(height_lbound) > Number(height_rbound)) {
                throw new Error(`Resize node ${n.id}: Height lower bound (${height_lbound}) cannot be greater than upper bound (${height_rbound})`);
            }

            op = `.map(MapResizeImage(${width_lbound},${width_rbound},${height_lbound},${height_rbound}))`;
        }
        if (t === 'llm') {

            const prompti = getNodeParameters(n);
            const prompt_F = prompti.prompt || 'Default Prompt: Describe what is in this image.';
            const model = prompti.subtype || 'llava';
            op = `.map(MapPromptLLM("""${prompt_F}""", """${model}"""))`;
        }
        if (t === 'grayscale') op = `.map(MapRecolorImage())`;




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
            const winParameter = (winParam.window_size !== undefined && winParam.window_size !== null && winParam.window_size !== '')
                ? Number(winParam.window_size)
                : 10;

            op = `.map(MapChangeFormat()).window_all(TumblingEventTimeWindows.of(Time.seconds(${winParameter}))).reduce(ReduceWindowResults())`;
        }

        //if (t === 'aggr') op = `.reduce(ReduceWindowResults())`;


        code += `\n# Procesing Node ${i + 1} (${t})`;
        code += `\n${next} = ${current}${op}`;
        current = next;
    });


    //Kafka Sink Out
    const endParameters = getNodeParameters(endNode);
    const server_out = endParameters.server || 'No_Server_Given_Out';
    const topic_out = endParameters.topic || 'No_Topic_Given_Out';

    code += `\n\nkafka_sink = KafkaSink.builder()\\
  .set_bootstrap_servers("${server_out}")\\
  .set_record_serializer(KafkaRecordSerializationSchema.builder()\\
       .set_topic("${topic_out}")\\
       .set_value_serialization_schema(SimpleStringSchema())\\
       .build())\\
  .build()

${current}.map(lambda x: ujson.dumps(x)).map(lambda x: x, Types.STRING()).sink_to(kafka_sink)

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

