import { nodeTypes } from "../../../components/nodes/defaultNodes.js";

export function getNodeParameters(node) {
    const foundNode = nodeTypes.find(n => n.label.toLowerCase() === (node.data?.label || '').toLowerCase());

    // Start with params from node object (may be empty)
    let params = { ...(node.params || {}) };

    if (!foundNode) {
        // If we don't have metadata for this node, return whatever params were saved on the node
        return params;
    }

    const hasSubtypes = Array.isArray(foundNode.subtypes) && foundNode.subtypes.length > 0;

    const nodeElement = document.querySelector(`[data-id="${node.id}"]`);
    if (!nodeElement) {
        // DOM not rendered for this node; return existing params but attempt to include subtype if present on node
        if (hasSubtypes && node.subtype) params.subtype = node.subtype;
        return params;
    }

    const selectedSubtype = hasSubtypes ? nodeElement.querySelector('select')?.value : undefined;
    const subtypeObj = hasSubtypes ? (foundNode.subtypes || []).find(s => s.subtype === selectedSubtype) : null;
    const paramsToSet = hasSubtypes ? (subtypeObj?.params || []) : (foundNode.params || []);

    const descriptionNode = nodeElement.querySelector('.description-node');
    if (descriptionNode) {
        paramsToSet.forEach(param => {
            const el = document.getElementById(param.id + "-" + node.id);
            if (el) {
                const val = (typeof el.value === 'string') ? el.value.trim() : (el.value ?? '');
                // Only override if DOM has a non-empty value; preserve node.params otherwise
                if (val !== '') {
                    params[param.name] = val;
                }
            }
        })
    }

    // Add subtype to params for nodes that have subtypes (like LLM model selection)
    if (hasSubtypes && selectedSubtype) {
        params.subtype = selectedSubtype;
    } else if (hasSubtypes && node.subtype) {
        // fallback to saved node subtype if select not present
        params.subtype = node.subtype;
    }

    return params;
}