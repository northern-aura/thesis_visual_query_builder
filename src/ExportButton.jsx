import React from 'react';
import { generateStructuredJSON } from './exportJson';
import { parseJsonToPython } from './flinkParser'; // placeholder

export default function ExportButton({ nodes, edges }) {
    const handleExport = () => {
        const jsonData = generateStructuredJSON(nodes, edges);

        // Validate: Ensure each node has at most 1 prev and 1 next
        const nextCount = {};
        const prevCount = {};

        edges.forEach(edge => {
            nextCount[edge.source] = (nextCount[edge.source] || 0) + 1;
            prevCount[edge.target] = (prevCount[edge.target] || 0) + 1;
        });

        const invalidNodes = nodes.filter(node => {
            const incoming = prevCount[node.id] || 0;
            const outgoing = nextCount[node.id] || 0;
            if (node.type === "source") {
                // Source: only one output, no input
                return !(incoming === 0 && outgoing === 1);
            } else if (node.type === "output") {
                // Output: only one input, no output
                return !(incoming === 1 && outgoing === 0);
            } else {
                // All others: one input and one output
                return !(incoming === 1 && outgoing === 1);
            }
        });

        if (invalidNodes.length > 0) {
            alert(
                "Invalid flow:\n" +
                invalidNodes.map(n =>
                    `Node "${n.data?.label || n.id}" (type: ${n.type}) is not connected correctly.`
                ).join('\n')
            );
            console.warn("Invalid nodes:", invalidNodes);
            return;
        }

        // Download the JSON
        const jsonString = JSON.stringify(jsonData, null, 2);
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'pipeline.json';
        a.click();
        URL.revokeObjectURL(url);

        //Placeholder for Flink Python generation
        const pythonCode = parseJsonToPython(jsonData);
        console.log("Generated Python (placeholder):\n", pythonCode);
    };

    return (
        <button
            onClick={handleExport}
            style={{
                position: 'absolute',
                bottom: '20px',
                right: '20px',
                padding: '16px 24px',
                fontSize: '18px',
                backgroundColor: '#d66',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                fontWeight: 'bold',
                cursor: 'pointer',
                boxShadow: '0 2px 6px rgba(0,0,0,0.15)',
                zIndex: 10
            }}
        >
            Export JSON
        </button>
    );
}
