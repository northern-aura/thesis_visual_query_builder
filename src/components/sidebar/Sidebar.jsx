import { CircleNode } from "../nodes/Nodes.jsx";
import "./Sidebar.css"
import { nodeTypes } from "../nodes/defaultNodes.ts";
import PresetQueryList from "../queries-list/PresetQueryList.jsx";
import { queryGroups } from "../queries-list/queries.js";
import { useState, useRef, useCallback, useEffect } from "react";
import CustomNodeModal from "../custom-nodes/CustomNodeModal.jsx";
import settingsIcon from "../../assets/icons/icons8-einstellungen.svg";

const MIN_SIDEBAR_WIDTH = 220;
const MAX_SIDEBAR_WIDTH = 600;
const DEFAULT_SIDEBAR_WIDTH = 270;

export default function Sidebar({ addNode, loadPresetQuery, collapsed, setCollapsed, sidebarWidth: controlledWidth, setSidebarWidth: setControlledWidth, customNodes = [], onSaveCustomNode, onOpenMetricsDashboard }) {
    // allow component to be controlled by parent; fall back to internal state when not provided
    const [localCollapsed, setLocalCollapsed] = useState(false);
    const [showCustomNodeModal, setShowCustomNodeModal] = useState(false);
    const [localWidth, setLocalWidth] = useState(DEFAULT_SIDEBAR_WIDTH);
    const isResizing = useRef(false);
    const sidebarRef = useRef(null);

    const sidebarWidth = controlledWidth ?? localWidth;
    const setSidebarWidth = setControlledWidth ?? setLocalWidth;

    const collapsedState = typeof collapsed !== 'undefined' ? collapsed : localCollapsed;
    const toggleCollapsed = () => {
        if (typeof setCollapsed === 'function') {
            setCollapsed(!collapsedState);
        } else {
            setLocalCollapsed(prev => !prev);
        }
    };

    // Drag-to-resize handler
    const handleResizeStart = useCallback((e) => {
        e.preventDefault();
        isResizing.current = true;
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    }, []);

    useEffect(() => {
        const handleMouseMove = (e) => {
            if (!isResizing.current) return;
            // sidebar left is 12px, so width = mouse X - 12
            const newWidth = Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, e.clientX - 12));
            setSidebarWidth(newWidth);
        };
        const handleMouseUp = () => {
            if (isResizing.current) {
                isResizing.current = false;
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }
        };
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
        return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        };
    }, [setSidebarWidth]);

    // Merge custom nodes with default nodes
    const allNodeTypes = [...nodeTypes, ...customNodes];
    const functionOptions = allNodeTypes
        .filter(node => node.functionType !== "source")
        .filter(node => !node.isDefault)
        .sort((a, b) => a.label.localeCompare(b.label));

    // Calculate grid columns based on sidebar width
    const gridCols = sidebarWidth >= 360 ? 4 : sidebarWidth >= 280 ? 3 : 2;

    return (
        <>
            <button
                className={`collapse-button ${collapsedState ? 'is-collapsed' : ''}`}
                onClick={toggleCollapsed}
                title={collapsedState ? 'Expand sidebar' : 'Collapse sidebar'}
                style={!collapsedState ? { left: `calc(12px + ${sidebarWidth}px + 6px)` } : undefined}
            >
                {collapsedState ? "»" : "«"}
            </button>

            <div
                ref={sidebarRef}
                className={`sidebar ${collapsedState ? "collapsed" : ""}`}
                style={{ width: `${sidebarWidth}px` }}
            >
                <h3>Function Options</h3>
                <FunctionOptions
                    options={functionOptions}
                    addNode={addNode}
                    onCreateCustomNode={() => setShowCustomNodeModal(true)}
                    gridCols={gridCols}
                />
                <br />
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <h3>Predefined queries</h3>
                    {onOpenMetricsDashboard && (
                        <button
                            onClick={onOpenMetricsDashboard}
                            className="btn-metrics-dashboard"
                            title="Open Metrics Dashboard to run all queries"
                        >
                            Run All
                        </button>
                    )}
                </div>
                <PresetQueryList queryGroups={queryGroups} loadPresetQuery={loadPresetQuery}></PresetQueryList>

                {/* Drag handle for resizing */}
                <div className="sidebar-resize-handle" onMouseDown={handleResizeStart} />
            </div>

            {showCustomNodeModal && (
                <CustomNodeModal
                    onSave={onSaveCustomNode}
                    onClose={() => setShowCustomNodeModal(false)}
                />
            )}
        </>
    );
}


function FunctionOptions({ options, addNode, onCreateCustomNode, gridCols = 3 }) {
    return (
        <div className="function-options-grid" style={{ gridTemplateColumns: `repeat(${gridCols}, 1fr)` }}>
            {options.map(option =>
                <div key={option.label} className="grid-item" onClick={() => addNode(option.label, 'function')}>
                    <CircleNode label={option.label} nodeType={option.label.toLowerCase()} icon={option.icon} />
                    <span className="grid-item-label">{option.label.toLowerCase() === 'llm' ? 'LLM' : option.label}</span>
                </div>
            )}
            {/* Add Custom Node card */}
            <div key="add-custom" onClick={onCreateCustomNode} className="add-custom-node-card grid-item">
                <div className="add-custom-circle">
                    <div className="node-circle">
                        <img src={settingsIcon} alt="Custom" style={{ width: '32px', height: '32px' }} />
                    </div>
                </div>
                <span className="grid-item-label">Custom</span>
            </div>
        </div>
    )
}