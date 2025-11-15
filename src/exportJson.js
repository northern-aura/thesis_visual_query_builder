export function generateStructuredJSON(nodes, edges) {
    const edgeMap = {
        next: {},
        prev: {},
    };

    edges.forEach(edge => {
        edgeMap.next[edge.source] = edge.target;
        edgeMap.prev[edge.target] = edge.source;
    });

    const result = nodes.map(node => {
        const id = node.id;
        const type = node.type;
        const { subtype, params } = node.data || {};

        return {
            id,
            type,
            subtype: subtype || null,
            params: params || {},
            nextNode: edgeMap.next[id] || "null",
            prevNode: edgeMap.prev[id] || "null"
        };
    });

    return result;
}
