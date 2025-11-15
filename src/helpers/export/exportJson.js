import {getNodeParameters} from "./utils/export-utils.js";
import {nodeTypes} from "../../components/nodes/defaultNodes.js";

export function generateStructuredJSON(nodes, edges) {
    // build maps of outgoing/incoming connections
    const edgeMap = { next: {}, prev: {} };
    edges.forEach(edge => {
        edgeMap.next[edge.source] = edge.target;
        edgeMap.prev[edge.target] = edge.source;
    });

    return nodes.map(node => {
        const foundNode = nodeTypes.find(n => n.label.toLowerCase() === node.data?.label.toLowerCase());
        // pull out the bits we need, with defaults
        const {
            id,
            type: defaultType,
            data: { nodeType } = {}
        } = node;

        const type = nodeType || defaultType;

        // Read subtype from DOM
        let subtypeFromDOM = null;
        const selectElementId = `subtype-select-${id}`;
        const selectElement = document.getElementById(selectElementId);
        if (selectElement) {
            subtypeFromDOM = selectElement.value;
        }

        const params = getNodeParameters(node);

        return {
            id,
            type,
            subtype: subtypeFromDOM,
            params,
            nextNode: edgeMap.next[id] ?? null,
            prevNode: edgeMap.prev[id] ?? null
        };
    });
}
