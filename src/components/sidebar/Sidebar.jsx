import { CircleNode } from "../nodes/Nodes.jsx";
import "./Sidebar.css"
import { nodeTypes } from "../nodes/defaultNodes.ts";
import PresetQueryList from "../queries-list/PresetQueryList.jsx";
import { queries } from "../queries-list/queries.js";
import { useState } from "react";

export default function Sidebar({ addNode, loadPresetQuery, collapsed, setCollapsed }) {
    // allow component to be controlled by parent; fall back to internal state when not provided
    const [localCollapsed, setLocalCollapsed] = useState(false);
    const collapsedState = typeof collapsed !== 'undefined' ? collapsed : localCollapsed;
    const toggleCollapsed = () => {
        if (typeof setCollapsed === 'function') {
            setCollapsed(!collapsedState);
        } else {
            setLocalCollapsed(prev => !prev);
        }
    };

    const functionOptions = nodeTypes
        .filter(node => node.functionType !== "source")
        .filter(node => !node.isDefault)
        .sort((a, b) => a.label.localeCompare(b.label));

    return (
        <>
            <button
                className={`collapse-button ${collapsedState ? 'is-collapsed' : ''}`}
                onClick={toggleCollapsed}
                title={collapsedState ? 'Expand sidebar' : 'Collapse sidebar'}
            >
                {collapsedState ? "»" : "«"}
            </button>

            <div className={`sidebar ${collapsedState ? "collapsed" : ""}`}>
                <h3>Function Options</h3>
                <FunctionOptions options={functionOptions} addNode={addNode} />
                <br />
                <h3>Predefined queries</h3>
                <PresetQueryList queries={queries} loadPresetQuery={loadPresetQuery}></PresetQueryList>
            </div>
        </>
    );
}


function FunctionOptions({ options, addNode }) {
    return (
        <div className="function-options-grid">
            {options.map(option =>
                <div key={option.label} onClick={() => addNode(option.label, 'function')}>
                    <CircleNode label={option.label} nodeType={option.label.toLowerCase()} icon={option.icon} />
                </div>)}
        </div>
    )
}