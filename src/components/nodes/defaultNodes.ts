
export const nodeTypes: DefaultType[] = [
    {
        isDefault: true,
        functionType: "start",
        label: 'Kafka Source',
        color: 'BlanchedAlmond',
        icon: "",
        subtypes: [],
        params: [
            { name: 'server', type: 'text', label: "Server", id: 'kafka-source-server' },
            { name: 'group_id', type: 'text', label: "Group ID", id: 'kafka-source-group_id' },
            { name: 'topic', type: 'text', label: "Topic", id: 'kafka-source-server-topic' }
        ]
    },
    {
        isDefault: true,
        functionType: "end",
        label: 'Kafka Sink',
        color: 'BlanchedAlmond',
        icon: "",
        subtypes: [],
        params: [
            { name: 'server', type: 'text', label: "Server", id: 'kafka-sink-server' },
            { name: 'topic', type: 'text', label: "Topic", id: 'kafka-sink-topic' }
        ]
    },
    {
        functionType: "map",
        label: 'Decode',
        color: 'powderblue',
        icon: "fa-key",
        info: "b64 algorithm",
        subtypes: [],
        params: []
    },
    {
        functionType: "map",
        label: 'LLM',
        color: 'MistyRose',
        icon: "fa-robot",
        subtypes: [
            {
                label: 'GPT-4o-mini (OpenAI)',
                subtype: 'gpt-4o-mini',
                id: "gpt-4o-mini",
                params: [
                    { name: 'prompt', type: 'text', label: "Prompt", isTextarea: true, id: "llm_prompt" }
                ]
            },
            {
                label: 'LLaVA (Ollama)',
                subtype: 'llava',
                id: "llava",
                params: [
                    { name: 'prompt', type: 'text', label: "Prompt", isTextarea: true, id: "llm_prompt" }
                ]
            },
            {
                label: 'LLaVA-Llama3 (Ollama)',
                subtype: 'llava-llama3',
                id: "llava-llama3",
                params: [
                    { name: 'prompt', type: 'text', label: "Prompt", isTextarea: true, id: "llm_prompt" }
                ]
            },
            {
                label: 'Gemma3:4b (Ollama)',
                subtype: 'gemma3:4b',
                id: "gemma3-4b",
                params: [
                    { name: 'prompt', type: 'text', label: "Prompt", isTextarea: true, id: "llm_prompt" }
                ]
            },
            {
                label: 'Llama3.2-Vision (Ollama)',
                subtype: 'llama3.2-vision',
                id: "llama3-2-vision",
                params: [
                    { name: 'prompt', type: 'text', label: "Prompt", isTextarea: true, id: "llm_prompt" }
                ]
            },
            {
                label: 'Mistral-Small3.1 (Ollama)',
                subtype: 'mistral-small3.1',
                id: "mistral-small3-1",
                params: [
                    { name: 'prompt', type: 'text', label: "Prompt", isTextarea: true, id: "llm_prompt" }
                ]
            }
        ],
        params: []
    },
    {
        functionType: "map",
        label: 'Resize',
        color: 'PaleGoldenRod',
        icon: "fa-expand",
        subtypes: [],
        params: [
            { name: 'width_lbound', type: 'number', label: "Width Lower Bound", id: "resize-width-lbound" },
            { name: 'width_rbound', type: 'number', label: "Width Upper Bound", id: "resize-width-rbound" },
            { name: 'height_lbound', type: 'number', label: "Height Lower Bound", id: "resize-height-lbound" },
            { name: 'height_rbound', type: 'number', label: "Height Upper Bound", id: "resize-height-rbound" }
        ]
    },
    {
        functionType: "map",
        label: 'Grayscale',
        info: "B+W Frame",
        color: 'lightgrey',
        icon: "fa-circle-half-stroke",
        subtypes: [],
        params: [],
    },
    {
        functionType: "window",
        label: 'Window',
        info: "Window + Collect",
        color: 'LightSkyBlue',
        icon: "fa-window-restore",
        subtypes: [],
        params: [
            { name: 'window_size', type: 'text', label: "Window Size", id: "Window_Size" }
        ]
    },
    {
        functionType: "aggr",
        label: 'Aggr',
        info: "Agregation",
        color: 'plum',
        icon: "fa-chart-bar",
        subtypes: []
    },
    {
        functionType: "filter",
        label: 'Filter',
        color: 'Pink',
        icon: "fa-filter",
        subtypes: [
            {
                label: 'Remove Empty Values',
                subtype: 'remove_empty_values',
                id: "remove-empty-values",
                params: []
            },
            {
                label: 'Remove Skipped',
                subtype: 'remove_skipped',
                id: "remove-skipped",
                params: []
            },
            {
                label: 'Remove Count < M',
                subtype: 'remove_count_less_than',
                id: "remove-count-less-than",
                params: [
                    { name: 'Remove Values Less Than', type: 'text', label: "Remove Values Less Than", id: "Remove_Values_Less" }
                ]
            }
        ]
    },

]

interface DefaultType {
    functionType: string,
    label: string,
    color: string,
    icon: string,
    subtypes?: Subtype[],
    params?: Param[],
    info?: string,
    isDefault?: boolean,
}

interface Subtype {
    id: string,
    label: string,
    subtype: string,
    params?: Param[]
}

interface Param {
    id: string,
    name: string,
    label: string,
    type: string,
    isTextarea?: boolean,
}