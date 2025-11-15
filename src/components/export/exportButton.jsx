import React, { useState, useEffect, useRef } from 'react';
import { generateStructuredJSON } from '../../helpers/export/exportJson';
import { generateDirectPython } from '../../helpers/export/directPythonExport'; // Import the new direct export
import pngIconLight from '../../assets/Screenshot button.png';
import pngIconDark from '../../assets/Dark Mode Screenshot button.png'; // Add this import at the top (place your PNG in src/assets/)

export default function ExportButton({ nodes, edges, projectName, onExportPng, onFileUpload }) {
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [fileInputKey, setFileInputKey] = useState(0); // for resetting file input
    const [isDarkMode, setIsDarkMode] = useState(false);    // Monitor dark mode changes
    const fileInputRef = useRef(null);
    useEffect(() => {
        // Initial check
        const checkDarkMode = () => {
            const darkModeActive = document.body.classList.contains('xy-dark');
            console.log('Dark mode check:', darkModeActive, 'Body classes:', document.body.className);
            setIsDarkMode(darkModeActive);
        };

        checkDarkMode();

        // Create observer to watch for class changes on body
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    checkDarkMode();
                }
            });
        });

        observer.observe(document.body, {
            attributes: true,
            attributeFilter: ['class']
        });

        return () => observer.disconnect();
    }, []);// Helper function for hover effects
    const getHoverStyle = (isHover) => {
        if (isDarkMode) {
            return isHover ? '#3a3a3a' : 'transparent';
        } else {
            return isHover ? '#f5f5f5' : 'transparent';
        }
    };

    const handleExportJson = () => {
        setIsMenuOpen(false); // Close menu after action
        // ...existing code... // Renamed for clarity
        const jsonData = generateStructuredJSON(nodes, edges);

        console.log(nodes)
        console.log(edges)
        // count incoming and outgoing per node
        const nextCount = {};
        const prevCount = {};
        edges.forEach(edge => {
            nextCount[edge.source] = (nextCount[edge.source] || 0) + 1;
            prevCount[edge.target] = (prevCount[edge.target] || 0) + 1;
        });

        // find start/end
        const startNodes = nodes.filter(n => n.type === 'start');
        const endNodes = nodes.filter(n => n.type === 'end');
        const errors = [];

        if (startNodes.length !== 1) {
            errors.push(`Expected exactly one start node, found ${startNodes.length}.`);
        }
        if (endNodes.length !== 1) {
            errors.push(`Expected exactly one end node, found ${endNodes.length}.`);
        }

        if (errors.length === 0) {
            const startId = startNodes[0].id;
            const endId = endNodes[0].id;

            // start must have 1 output
            const startOut = nextCount[startId] || 0;
            if (startOut !== 1) {
                errors.push(`Start node "Kafka Sink 1" must have exactly one output, found ${startOut}.`);
            }

            // end must have 1 input
            const endIn = prevCount[endId] || 0;
            if (endIn !== 1) {
                errors.push(`End node "Kafka Sink 2" must have exactly one input, found ${endIn}.`);
            }

            // all others must have one in and one out
            nodes.forEach(node => {
                const type = node.type;
                if (type === 'start' || type === 'end') return;
                const incoming = prevCount[node.id] || 0;
                const outgoing = nextCount[node.id] || 0;
                if (incoming !== 1 || outgoing !== 1) {
                    errors.push(
                        `Node "${type || node.id}" must have exactly one input and one output (in: ${incoming}, out: ${outgoing}).`
                    );
                }
            });
        }

        if (errors.length > 0) {
            alert('Invalid flow:\n' + errors.join('\n'));
            return;
        }

        // download JSON
        const exportData = {
            "name of project": projectName || "Untitled Project",
            nodes: jsonData
        };
        const jsonString = JSON.stringify(exportData, null, 2);
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${projectName || 'pipeline'}.json`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const handleExportPythonDirect = () => {
        setIsMenuOpen(false); // Close menu after action
        try {
            const jsonData = generateStructuredJSON(nodes, edges);

            const blob = new Blob([pythonCode], { type: 'text/x-python' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${projectName || 'pipeline'}.py`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error("Error generating Python code:", error);
            alert("Error generating Python code. Please check your pipeline configuration.\n\nError: " + error.message);
        }
    };

    // Helper function to transform node types from JSON to expected labels
    const transformNodeTypeToLabel = (nodeType) => {
        const typeMapping = {
            'start': 'Kafka Sink 1',
            'end': 'Kafka Sink 2',
            'source': 'Source',
            'decode': 'Decode',
            'resize': 'Resize',
            'llm': 'LLM',
            'grayscale': 'Grayscale',
            'filter': 'Filter'
        };
        return typeMapping[nodeType] || nodeType;
    };

    const handleExportDirectPython = () => {
        setIsMenuOpen(false); // Close menu after action
        try {
            const pythonCode = generateDirectPython(nodes, edges, projectName);

            const blob = new Blob([pythonCode], { type: 'text/x-python' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${projectName || 'pipeline'}_direct.py`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error("Error generating direct Python code:", error);
            alert("Error generating direct Python code. Please check your pipeline configuration.\n\nError: " + error.message);
        }
    };

    return (
        <>
            {/* Screenshot Button at the top right */}
            <div style={{
                position: 'absolute',
                top: '20px',
                right: '20px',
                zIndex: 10
            }}>                <button
                className="screenshot-button"
                onClick={onExportPng}
                style={{
                    padding: '12px 14px',
                    fontSize: '16px',
                    backgroundColor: isDarkMode ? '#2a2a2a' : 'white',
                    color: isDarkMode ? '#e0e0e0' : '#333',
                    border: isDarkMode ? '1px solid #555' : '1px solid #ccc',
                    borderRadius: '8px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    boxShadow: '0 2px 6px rgba(0,0,0,0.10)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    transition: 'all 0.2s ease'
                }}
                title="Export as PNG"
            >
                    <img src={isDarkMode ? pngIconDark : pngIconLight} alt="PNG Export" style={{ width: 22, height: 22 }} />
                </button>
            </div>            {/* Main Export Dropdown Button at the bottom right */}
            <div className="export-button" style={{
                position: 'absolute',
                bottom: '20px',
                right: '20px',
                zIndex: 10
            }}>
                <button
                    className="export-menu-button"
                    onClick={() => setIsMenuOpen(!isMenuOpen)}
                    style={{
                        backgroundColor: '#20A678',
                        color: 'white',
                        border: 'none',
                        fontSize: '18px'
                    }}
                >
                    Menu
                    <span style={{
                        transform: isMenuOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                        transition: 'transform 0.2s ease'
                    }}>
                        ▼
                    </span>
                </button>                {/* Dropdown Menu */}
                {isMenuOpen && (
                    <div className="export-dropdown" style={{
                        position: 'absolute',
                        bottom: '100%',
                        right: '0',
                        marginBottom: '8px',
                        backgroundColor: 'white',
                        border: '1px solid #ddd',
                        borderRadius: '8px',
                        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                        overflow: 'hidden',
                        minWidth: '180px',
                        zIndex: 100
                    }}>                        <button
                        onClick={handleExportJson}
                        style={{
                            width: '100%',
                            padding: '12px 16px',
                            fontSize: '14px',
                            backgroundColor: 'transparent',
                            color: '#333',
                            border: 'none',
                            borderBottom: '1px solid #eee',
                            cursor: 'pointer',
                            textAlign: 'left',
                            transition: 'background-color 0.2s ease'
                        }}
                        onMouseEnter={e => e.target.style.backgroundColor = getHoverStyle(true)}
                        onMouseLeave={e => e.target.style.backgroundColor = getHoverStyle(false)}
                    >
                            Export JSON
                        </button>                        <button
                            onClick={handleExportDirectPython}
                            style={{
                                width: '100%',
                                padding: '12px 16px',
                                fontSize: '14px',
                                backgroundColor: 'transparent',
                                color: '#333',
                                border: 'none',
                                borderBottom: '1px solid #eee',
                                cursor: 'pointer',
                                textAlign: 'left',
                                transition: 'background-color 0.2s ease'
                            }}
                            onMouseEnter={e => e.target.style.backgroundColor = getHoverStyle(true)}
                            onMouseLeave={e => e.target.style.backgroundColor = getHoverStyle(false)}
                        >
                            Export Python
                        </button>                        <div className="export-dropdown-item" style={{
                            borderTop: 'none',
                            width: '100%',
                            padding: '12px 16px',
                            fontSize: '14px',
                            backgroundColor: 'transparent',
                            color: '#333',
                            border: 'none',
                            cursor: 'pointer',
                            textAlign: 'left',
                            transition: 'background-color 0.2s ease'
                        }} onMouseEnter={e => e.target.style.backgroundColor = getHoverStyle(true)}
                            onMouseLeave={e => e.target.style.backgroundColor = getHoverStyle(false)}
                            onClick={() => {
                                // clicking anywhere in this dropdown item should open the file chooser
                                if (fileInputRef.current) fileInputRef.current.click();
                            }}>
                            <label htmlFor="choose-file" className="export-dropdown-label" style={{ fontSize: '14px', color: '#333', cursor: 'pointer', fontWeight: '' }}>
                                Import JSON
                            </label>
                            <input
                                id="choose-file"
                                ref={fileInputRef}
                                key={fileInputKey}
                                type="file"
                                accept=".json"
                                style={{ display: 'none' }}
                                onChange={e => {
                                    if (onFileUpload) onFileUpload(e);
                                    setFileInputKey(prev => prev + 1); // reset input so same file can be chosen again
                                    setIsMenuOpen(false);
                                }}
                            />
                        </div>
                    </div>
                )}
            </div>
        </>
    );
}
