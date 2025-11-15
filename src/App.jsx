import React, {useCallback, useEffect, useRef, useState} from 'react';
import {
    addEdge,
    Background, ControlButton, Controls,
    getConnectedEdges,
    getIncomers,
    getOutgoers,
    MiniMap,
    Position,
    ReactFlow,
    MarkerType,
    useEdgesState,
    useNodesState
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './components/theme/xy.theme.css';
import FunctionNode, {BlockEndNode, BlockStartNode} from "./components/nodes/Nodes.jsx";
import ExportButton from './components/export/exportButton.jsx';
import Sidebar from "./components/sidebar/Sidebar.jsx";
import ThemeMenu from './components/theme/ThemeMenu.jsx';
import {toPng} from "html-to-image";
import {nodeTypes} from "./components/nodes/defaultNodes.js";


const nodeDefaults = {
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
};

const nodeTypesDefinition = {
    function: FunctionNode,

    start: BlockStartNode,
    end: BlockEndNode
}

const initialNodes = [
    {
        id: '1',
        position: {x: 200, y: 100},
        data: {label: 'Kafka Source'},
        ...nodeDefaults,
        type: 'start'
    },
    {
        id: '2',
        position: {x: 400, y: 100},
        data: {label: 'Kafka Sink'},
        ...nodeDefaults,
        type: 'end'
    },
];
const initialEdges = [{id: 'e1-2', source: '1', target: '2'}];


export default function App() {
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
    const [projectName, setProjectName] = useState('Untitled Project');
    const [showDarkMode, setShowDarkMode] = useState(false);
    const [colorMode, setColorMode] = useState('dark');

    const nodesDiagram = useRef(null);    // Move exportDiagram to a named function for PNG export
    const exportDiagram = () => {
        if (nodesDiagram.current === null) return;

        // Get the ReactFlow instance to access transform and viewport
        const reactFlowInstance = nodesDiagram.current.querySelector('.react-flow');
        if (!reactFlowInstance) return;        // Add export mode class to help with styling
        const exportContainer = nodesDiagram.current;
        exportContainer.classList.add('export-mode');

        // Preserve dark mode styling for proper colors in export
        const isDarkMode = document.body.classList.contains('xy-dark');
        if (isDarkMode) {
            exportContainer.classList.add('xy-dark');
        } else {
            exportContainer.classList.add('xy-light');
        }// Hide controls and other UI elements before export
        const controls = exportContainer.querySelector('.react-flow__controls');
        const originalControlsDisplay = controls ? controls.style.display : '';
        if (controls) {
            controls.style.display = 'none';
        }

        // Also hide attribution if present
        const attribution = exportContainer.querySelector('.react-flow__attribution');
        const originalAttributionDisplay = attribution ? attribution.style.display : '';
        if (attribution) {
            attribution.style.display = 'none';
        }

        // Hide minimap if present
        const minimap = exportContainer.querySelector('.react-flow__minimap');
        const originalMinimapDisplay = minimap ? minimap.style.display : '';
        if (minimap) {
            minimap.style.display = 'none';
        }        // Hide all resize controls and handles
        const resizeControls = exportContainer.querySelectorAll('.react-flow__resize-control, .react-flow__node-resizer');
        const originalResizeControlsDisplays = [];
        resizeControls.forEach((control, index) => {
            originalResizeControlsDisplays[index] = control.style.display;
            control.style.display = 'none';
        });

        // Force description nodes to have no scrollbars or rulers
        const descriptionNodes = exportContainer.querySelectorAll('.description-node');
        const originalDescriptionStyles = [];
        descriptionNodes.forEach((node, index) => {
            originalDescriptionStyles[index] = {
                overflow: node.style.overflow,
                overflowY: node.style.overflowY,
                overflowX: node.style.overflowX,
                scrollbarWidth: node.style.scrollbarWidth
            };
            node.style.overflow = 'hidden';
            node.style.overflowY = 'hidden';
            node.style.overflowX = 'hidden';
            node.style.scrollbarWidth = 'none';
        });// Calculate bounds of all nodes to capture the entire pipeline
        const padding = 100; // Reduced padding since we're hiding resize controls
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

        nodes.forEach(node => {
            const nodeWidth = 80; // Actual node circle diameter
            const nodeHeight = 80; // Actual node circle diameter  
            const descriptionHeight = 180; // Description box height (reduced from 200)
            const descriptionWidth = 160; // Description box width

            minX = Math.min(minX, node.position.x - Math.max(nodeWidth / 2, descriptionWidth / 2));
            minY = Math.min(minY, node.position.y - nodeHeight / 2);
            maxX = Math.max(maxX, node.position.x + Math.max(nodeWidth / 2, descriptionWidth / 2));
            maxY = Math.max(maxY, node.position.y + nodeHeight / 2 + descriptionHeight);
        });

        const bounds = {
            x: minX - padding,
            y: minY - padding,
            width: maxX - minX + 2 * padding,
            height: maxY - minY + 2 * padding
        };

        // Store original transform and viewport
        const viewport = reactFlowInstance.querySelector('.react-flow__viewport');
        const originalTransform = viewport ? viewport.style.transform : '';

        // Reset transform to show all nodes
        if (viewport) {
            viewport.style.transform = `translate(${-bounds.x}px, ${-bounds.y}px) scale(1)`;
        }

        // Set container size to fit all content
        const originalWidth = exportContainer.style.width;
        const originalHeight = exportContainer.style.height;
        const originalOverflow = exportContainer.style.overflow;

        exportContainer.style.width = `${bounds.width}px`;
        exportContainer.style.height = `${bounds.height}px`;
        exportContainer.style.overflow = 'visible';        // Wait a bit for the transform to apply
        setTimeout(() => {
            // Force all SVG elements to be visible
            const svgElements = exportContainer.querySelectorAll('svg');
            svgElements.forEach(svg => {
                svg.style.overflow = 'visible';
                svg.style.visibility = 'visible';
                svg.style.display = 'block';

                // Force all paths in SVG to be visible
                const edgeGray = '#888888';
                const paths = svg.querySelectorAll('path');
                paths.forEach(path => {
                    if (path.classList.contains('react-flow__edge-path')) {
                        path.style.visibility = 'visible';
                        path.style.display = 'block';
                        path.style.opacity = '1';
                        // Use a neutral gray for exported edges instead of pure black/white
                        path.style.stroke = edgeGray;
                        path.style.strokeWidth = '6px';
                        path.style.fill = 'none';
                    }
                });

                // Force markers to be visible and colored gray
                const markerPaths = svg.querySelectorAll('marker path, .react-flow__arrowhead');
                markerPaths.forEach(mp => {
                    try {
                        mp.style.fill = edgeGray;
                        mp.style.stroke = edgeGray;
                        mp.style.opacity = '1';
                    } catch (e) {
                        // ignore
                    }
                });
            });
            // Save original node label styles and turn node label text white just for the export
            const originalNodeLabelStyles = [];
            try {
                const nodeLabelEls = exportContainer.querySelectorAll('.node-label');
                nodeLabelEls.forEach(el => {
                    try {
                        originalNodeLabelStyles.push({el, color: el.style.color || '', fill: el.style.fill || ''});
                        el.style.color = '#ffffff';
                        el.style.fill = '#ffffff';
                    } catch (e) {
                    }
                });
            } catch (e) {
            }

            // Export with better options for edge visibility
            toPng(exportContainer, {
                cacheBust: true,
                backgroundColor: 'transparent',
                pixelRatio: 2,
                quality: 1.0,
                width: bounds.width,
                height: bounds.height,
                skipFonts: false,
                includeQueryParams: true,
                style: {
                    transform: 'scale(1)',
                    transformOrigin: 'top left',
                }, filter: (node) => {
                    // Exclude controls, attribution, background, minimap, resize controls
                    if (node.classList) {
                        return !node.classList.contains('react-flow__controls') &&
                            !node.classList.contains('react-flow__attribution') &&
                            !node.classList.contains('react-flow__background') &&
                            !node.classList.contains('react-flow__minimap') &&
                            !node.classList.contains('react-flow__resize-control') &&
                            !node.classList.contains('react-flow__node-resizer');
                    }
                    return true;
                }
            })
                .then((dataUrl) => {                    // Restore all original settings
                    exportContainer.classList.remove('export-mode');
                    exportContainer.classList.remove('xy-dark');
                    exportContainer.classList.remove('xy-light');
                    exportContainer.style.width = originalWidth;
                    exportContainer.style.height = originalHeight;
                    exportContainer.style.overflow = originalOverflow;
                    if (viewport) {
                        viewport.style.transform = originalTransform;
                    }
                    if (controls) {
                        controls.style.display = originalControlsDisplay;
                    }
                    if (attribution) {
                        attribution.style.display = originalAttributionDisplay;
                    }
                    if (minimap) {
                        minimap.style.display = originalMinimapDisplay;
                    }                    // Restore resize controls
                    resizeControls.forEach((control, index) => {
                        control.style.display = originalResizeControlsDisplays[index];
                    });
                    // Restore description node styles
                    descriptionNodes.forEach((node, index) => {
                        const original = originalDescriptionStyles[index];
                        node.style.overflow = original.overflow;
                        node.style.overflowY = original.overflowY;
                        node.style.overflowX = original.overflowX;
                        node.style.scrollbarWidth = original.scrollbarWidth;
                    });

                    // After export, restore original node label styles
                    try {
                        originalNodeLabelStyles.forEach(({el, color, fill}) => {
                            try {
                                el.style.color = color;
                                el.style.fill = fill;
                            } catch (e) {
                            }
                        });
                    } catch (e) {
                    }

                    const link = document.createElement('a');
                    link.download = `${projectName.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_full_pipeline.png`;
                    link.href = dataUrl;
                    link.click();
                }).catch((err) => {
                // Restore all elements even if export fails
                exportContainer.classList.remove('export-mode');
                exportContainer.classList.remove('xy-dark');
                exportContainer.classList.remove('xy-light');
                exportContainer.style.width = originalWidth;
                exportContainer.style.height = originalHeight;
                exportContainer.style.overflow = originalOverflow;

                if (viewport) {
                    viewport.style.transform = originalTransform;
                }
                if (controls) {
                    controls.style.display = originalControlsDisplay;
                }
                if (attribution) {
                    attribution.style.display = originalAttributionDisplay;
                }
                if (minimap) {
                    minimap.style.display = originalMinimapDisplay;
                }                    // Restore resize controls
                resizeControls.forEach((control, index) => {
                    control.style.display = originalResizeControlsDisplays[index];
                });
                // Restore description node styles
                descriptionNodes.forEach((node, index) => {
                    const original = originalDescriptionStyles[index];
                    node.style.overflow = original.overflow;
                    node.style.overflowY = original.overflowY;
                    node.style.overflowX = original.overflowX;
                    node.style.scrollbarWidth = original.scrollbarWidth;
                });
                // If export failed, restore original node label styles
                try {
                    originalNodeLabelStyles.forEach(({el, color, fill}) => {
                        try {
                            el.style.color = color;
                            el.style.fill = fill;
                        } catch (e) {
                        }
                    });
                } catch (e) {
                }

                console.error("Error downloading diagram:", err);
            });
        }, 100); // Small delay to ensure transform is applied
    };

    const onBeforeDelete =
        (deleted) => {
            // you can never delete start node or end node
            return !deleted.nodes.some(node => node.id === "1" || node.id === "2");
        }

    /**
     * This method deletes several nodes (holding Ctrl-key to delete more than one) from the diagram
     * and shifts all the right nodes from deleted 200px to left
     * if the middle node is deleted that the edges will automatically apply to deleted neighbours
     * @type {(function(*): void)|*}
     */
    const onNodesDelete = useCallback(
        (deleted) => {

            const mostLeftDeletedNodePosition = Math.min(...deleted.map(node => node.position.x));
            setNodes(nodes => {
                return nodes.map(node => {
                    if (node.position?.x >= mostLeftDeletedNodePosition) {
                        return {
                            ...node,
                            position: {
                                ...node.position,
                                x: node.position.x - 200,
                            }
                        };
                    }
                    return node;
                });
            });

            setEdges(
                deleted.reduce((acc, node) => {
                    const incomers = getIncomers(node, nodes, edges);
                    const outgoers = getOutgoers(node, nodes, edges);
                    const connectedEdges = getConnectedEdges([node], edges);

                    const remainingEdges = acc.filter(
                        (edge) => !connectedEdges.includes(edge),
                    );

                    const createdEdges = incomers.flatMap(({id: source}) =>
                        outgoers.map(({id: target}) => ({
                            id: `${source}->${target}`,
                            source,
                            target,
                        })),
                    );

                    return [...remainingEdges, ...createdEdges];
                }, edges),
            );
        },
        [setNodes, setEdges, edges, nodes],
    );

    const onConnect = useCallback(
        (params) => setEdges((eds) => addEdge(params, eds)),
        [setEdges],
    );
    const addNode = useCallback((label, type) => {

        const lastNodeIndex = nodes.findIndex((node) => node.type === 'end');
        const lastNode = nodes[lastNodeIndex];
        const lastNodeModified = {
            ...lastNode,
            position: {
                ...lastNode.position,
                x: lastNode.position.x + 200
            }
        };

        const lastEdge = edges.find((e) => e.target === lastNode.id);
        const penultId = lastEdge?.source;
        const maxId = Math.max(...nodes.map(node => +node.id))

        const newId = (maxId + 1).toString();
        const newNode = {
            id: newId,
            type: type,
            position: {
                x: lastNode.position.x,
                y: lastNode.position.y,
            },
            ...nodeDefaults,
            data: {label, nodeType: label.toLowerCase()},
        };

        setNodes(nodes => {
            const newNodes = [...nodes];
            newNodes[lastNodeIndex] = lastNodeModified;
            return [...newNodes, newNode]
        })

        setEdges(edges => {
            const filteredEdges = edges.filter(
                (e) => !(e.target === lastNode.id)
            );
            console.log('FilteredEdges:', filteredEdges.map((e) => e.id));
            return [...filteredEdges,
                {
                    id: `e-${penultId}-${newId}`,
                    source: penultId,
                    target: newId
                },
                {
                    id: `e-${newId}-${lastNode.id}`,
                    source: newId,
                    target: lastNode.id
                }
            ];
        });
    }, [nodes, setNodes, edges, setEdges]);

    const onFileUpload = async (event) => {
        const newNodes = await fileUpload(event);
        setTimeout(() => {
            setParamsValues(newNodes); // first load the nodes state and then set their params
        }, 1)
    }

    function getRestoredEdges(restoredNodes) {
        return restoredNodes?.map(node => {
            return {
                id: `e-${node.prevNode ? node.prevNode : 1}-${node.nextNode ? node.nextNode : 2}`,
                source: node.id,
                target: node.nextNode
            }
        });
    }

    const getNodesPositioned = useCallback((sorted) => {
        return sorted.map((node, i) => {
            return {
                ...node,
                position: {
                    x: i * 200,
                    y: 100,
                },
                data: {
                    label: isNode(node).blockType ? isNode(node).correctlyLabeled : convertNodeLabel(node.type),
                    nodeType: node.type
                },
                type: isNode(node).blockType ? node.type : "function",
            }
        });
    }, []);

    const fileUpload = useCallback((event) => {
            return new Promise((resolve) => {
                    const file = event.target.files[0];
                    if (!file) return;

                    const reader = new FileReader();
                    reader.onload = (e) => {
                        const content = e.target?.result;
                        const parsed = JSON.parse(content);

                        const restoredNodes = parsed?.nodes;
                        //first node is the one with no prev node but also type == start also id == 1 (?)
                        //need to specify if deleting start & end node are allowed
                        //also specify if only start has no prev and end has no next
                        const restoredEdges = restoredNodes.map(node => {
                            return {
                                id: `e-${node.prevNode ? node.prevNode : 1}-${node.nextNode ? node.nextNode : 2}`,
                                source: node.id,
                                target: node.nextNode
                            }
                        });

                        const sorted = sortByNext(restoredNodes);

                        const nodesPositioned = sorted.map((node, i) => {
                            return {
                                ...node,
                                position: {
                                    x: i * 200,
                                    y: 100,
                                },
                                data: {
                                    label: isNode(node).blockType ? isNode(node).correctlyLabeled : convertNodeLabel(node.type),
                                    nodeType: node.type
                                },
                                type: isNode(node).blockType ? node.type : "function",
                            }
                        });


                        setProjectName(() => parsed["name of project"]);
                        setNodes(() => [...nodesPositioned]);
                        setEdges(() => [...restoredEdges]);

                        requestAnimationFrame(() => {
                            resolve(nodesPositioned); //returning actual state of the nodes
                        })

                    };
                    reader.readAsText(file);

                }
            )
        }
        , [setNodes, setEdges]);

    const tidyUp = useCallback(() => {
        setNodes((nodes) => {
            // Kafka Sink should be at the end
            const special = nodes.find((n) => n.id === "2");
            const others = nodes.filter((n) => n.id !== "2");

            // сначала расставляем остальных
            const updatedOthers = others.map((node, i) => ({
                ...node,
                position: {
                    ...node.position,
                    x: i * 200,
                    y: 100,
                },
            }));

            const updatedSpecial = special
                ? {
                    ...special,
                    position: {
                        ...special.position,
                        x: updatedOthers.length * 200,
                        y: 100,
                    },
                }
                : null;

            return updatedSpecial ? [...updatedOthers, updatedSpecial] : updatedOthers;
        });
    }, [setNodes]);

    const loadPresetQuery = useCallback((query) => {
        const restoredNodes = query?.nodes;

        if (!restoredNodes) return
        const restoredEdges = restoredNodes.map(node => {
            return {
                id: `e-${node.prevNode ? node.prevNode : 1}-${node.nextNode ? node.nextNode : 2}`,
                source: node.id,
                target: node.nextNode
            }
        });

        const sorted = sortByNext(restoredNodes);

        const nodesPositioned = sorted.map((node, i) => {
            return {
                ...node,
                position: {
                    x: i * 200,
                    y: 100,
                },
                data: {
                    label: isNode(node).blockType ? isNode(node).correctlyLabeled : convertNodeLabel(node.type),
                    nodeType: node.type
                },
                type: isNode(node).blockType ? node.type : "function",
            }
        });

        setProjectName(() => query["title"]);
        setNodes(() => [...nodesPositioned]);
        setEdges(() => [...restoredEdges]);

        setTimeout(() => {
            setParamsValues(nodesPositioned); // first load the nodes state and then set their params
        }, 1)

    }, [setEdges, setNodes]);

    function setParamsValues(nodes) {
        nodes.forEach(n => {
            const foundNode = nodeTypes.find(node => node.label.toLowerCase() === (n.data?.label || '').toLowerCase());
            const nodeElement = document.querySelector(`[data-id="${n.id}"]`);
            const descriptionNode = nodeElement?.querySelector('.description-node');
            if (!descriptionNode) {
                // Node DOM not ready or missing - skip setting params for this node
                console.warn(`Description node not found for node ${n.id}`);
                return;
            }

            // If no matching node type found, skip
            if (!foundNode) {
                console.warn(`No node type definition found for ${n.data?.label} (node ${n.id})`);
                return;
            }

            const hasSubtypes = Array.isArray(foundNode.subtypes) && foundNode.subtypes.length > 0;
            if (!hasSubtypes) {
                (foundNode.params || []).forEach(p => {
                    const parameterInput = document.getElementById(`${p.id}-${n.id}`);
                    if (parameterInput) {
                        const val = n.params ? (n.params[p.name] ?? '') : '';
                        parameterInput.value = String(val);
                        parameterInput.title = String(val);
                    }
                });
            } else {
                const subtypeSelect = nodeElement.querySelector("select");
                const targetSubtype = n.subtype || (foundNode.subtypes[0] && foundNode.subtypes[0].subtype) || '';
                const foundSubtype = (foundNode.subtypes || []).find(s => s.subtype === targetSubtype);

                if (subtypeSelect) {
                    try {
                        subtypeSelect.value = targetSubtype;
                        subtypeSelect.dispatchEvent(new Event("change", {bubbles: true}));
                    } catch (e) {
                        console.log(e)
                    }
                }

                if (foundSubtype && Array.isArray(foundSubtype.params)) {
                    foundSubtype.params.forEach(p => {
                        const parameterInput = document.getElementById(`${p.id}-${n.id}`);
                        if (parameterInput) {
                            const val = n.params ? (n.params[p.name] ?? '') : '';
                            parameterInput.value = String(val);
                            parameterInput.title = String(val);
                        }
                    });
                }
            }
        })
    }

    function convertNodeLabel(str) {
        const [first, ...rest] = str;
        return first.toUpperCase() + rest.join("");
    }

    function isNode(node) {
        return {
            blockType: node.type === "start" || node.type === "end",
            correctlyLabeled: node.type === "start" ? "Kafka Source" : "Kafka Sink",
        };
    }

    function sortByNext(nodes) {
        const nodeMap = Object.fromEntries(nodes.map((node) => [node.id, node]));

        const sorted = [];
        let current = nodes.find(node => node.id === "1");
        while (current) {
            sorted.push(current);
            current = current.nextNode ? nodeMap[current.nextNode] : null;
        }
        return sorted;

    }

    const dropHandler = useCallback((event) => {
        event.preventDefault();
        console.log(event.dataTransfer.items);

    }, []);

    const onDragOverHandler = useCallback((event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
    }, []);

    useEffect(() => {
        if (colorMode === 'dark') {
            document.body.classList.add('xy-dark');
            document.body.classList.remove('xy-light');
        } else if (colorMode === 'light') {
            document.body.classList.add('xy-light');
            document.body.classList.remove('xy-dark');
        } else {
            // system: use prefers-color-scheme
            const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            document.body.classList.toggle('xy-dark', isDark);
            document.body.classList.toggle('xy-light', !isDark);
        }
    }, [colorMode]);

    return (
        <div style={{width: '100vw', height: '100vh'}} className="outer"
             tabIndex={0}>            {/* Dark mode selector */}
            <div style={{
                position: 'absolute',
                bottom: 20,
                right: 150,
                zIndex: 2000,
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
            }}>
                {/* theme button placed above the main export Menu for visual grouping */}
                <ThemeMenu currentMode={colorMode} onChangeMode={(m) => setColorMode(m)}/>
            </div>
            {/* Title input at the top middle */}
            <div className="project-name-input" style={{
                position: 'absolute',
                top: '20px',
                left: '50%',
                transform: 'translateX(-50%)',
                zIndex: 1000,
                padding: '10px 20px',
                borderRadius: '12px',
                width: 500
            }}>
                <input
                    type="text"
                    value={projectName || ""}
                    onChange={(e) => setProjectName(e.target.value)}
                    placeholder="Enter project name..."
                    style={{
                        border: 'none',
                        outline: 'none',
                        fontSize: '16px',
                        fontWeight: 'bold',
                        textAlign: 'center',
                        minWidth: '200px',
                        background: 'transparent',
                        width: '100%'
                    }}
                />
            </div>

            <Sidebar addNode={addNode} loadPresetQuery={loadPresetQuery} collapsed={sidebarCollapsed}
                     setCollapsed={setSidebarCollapsed}/>
            <div style={{width: '100vw', height: '100vh'}}>
                {/* Export Button in bottom right */}
                <ExportButton
                    nodes={nodes}
                    edges={edges}
                    projectName={projectName}
                    onExportPng={exportDiagram}
                    onFileUpload={onFileUpload}
                />
                <div id="dropZone" onDrop={dropHandler} onDragOver={onDragOverHandler} ref={nodesDiagram}
                     style={{width: '100vw', height: '100vh'}}>
                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        nodeTypes={nodeTypesDefinition}
                        defaultEdgeOptions={{markerEnd: {type: MarkerType.ArrowClosed, width: 7, height: 7}}}
                        onBeforeDelete={onBeforeDelete}
                        onNodesDelete={onNodesDelete}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onConnect={onConnect}
                        colorMode={colorMode}
                        fitView
                    >
                        <Controls
                            style={{
                                left: sidebarCollapsed ? '18px' : 'calc(12px + 270px + 24px)',
                                bottom: '12px',
                                position: 'absolute',
                                width: '25px',
                                zIndex: 3000,
                                transition: 'left 200ms ease, bottom 200ms ease'
                            }}
                        >
                            <ControlButton
                                onClick={tidyUp}
                                title="Tidy Up - Organize nodes in a clean layout">
                                🧹
                            </ControlButton>
                            <div> {/* intentional empty, do not remove */}</div>
                        </Controls>
                        <Background/>
                    </ReactFlow>
                </div>
            </div>
        </div>
    );

}