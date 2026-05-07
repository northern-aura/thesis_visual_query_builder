/**
 * ResultsPanel component - Bottom drawer for execution results
 */
import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { ExecutionSSEClient } from '../../services/sseClient';
import { KafkaSSEClient } from '../../services/kafkaSseClient';
import { backendClient } from '../../services/backendClient';
import LatencyCharts from './LatencyCharts';
import './ResultsPanel.css';

export default function ResultsPanel({ execution, onClose }) {
  const [logs, setLogs] = useState([]);
  const [kafkaMessages, setKafkaMessages] = useState([]);
  const [status, setStatus] = useState('starting');
  const [isConnected, setIsConnected] = useState(false);
  const [isKafkaConnected, setIsKafkaConnected] = useState(false);
  const [exitCode, setExitCode] = useState(null);
  const [duration, setDuration] = useState(null);
  const [isMinimized, setIsMinimized] = useState(false);
  const [activeView, setActiveView] = useState('logs'); // 'logs' | 'kafka' | 'charts'
  const [panelHeight, setPanelHeight] = useState(400);
  const [startTime, setStartTime] = useState(null);

  const logsEndRef = useRef(null);
  const kafkaEndRef = useRef(null);
  const sseClientRef = useRef(null);
  const kafkaClientRef = useRef(null);
  const isDragging = useRef(false);

  // Resize drag handling
  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = 'ns-resize';
    document.body.style.userSelect = 'none';
  }, []);

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging.current) return;
      const newHeight = Math.max(150, Math.min(window.innerHeight - 100, window.innerHeight - e.clientY));
      setPanelHeight(newHeight);
    };
    const handleMouseUp = () => {
      if (!isDragging.current) return;
      isDragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (!isMinimized && activeView === 'logs' && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, isMinimized, activeView]);

  // Auto-scroll to bottom when new Kafka messages arrive
  useEffect(() => {
    if (!isMinimized && activeView === 'kafka' && kafkaEndRef.current) {
      kafkaEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [kafkaMessages, isMinimized, activeView]);

  // Set up SSE connection
  useEffect(() => {
    if (!execution || !execution.execution_id) return;

    // Reset view state on new execution
    setLogs([]);
    setKafkaMessages([]);
    setActiveView('logs');
    setIsKafkaConnected(false);

    const sseClient = new ExecutionSSEClient(execution.execution_id, {
      connected: () => {
        setIsConnected(true);
      },
      started: (msg) => {
        setStatus('running');
        setStartTime(Date.now());
        addLog({ type: 'info', data: 'Execution started', timestamp: msg.timestamp });
      },
      docker_status: (msg) => {
        setStatus(msg.message);
        addLog({ type: 'info', data: msg.message, timestamp: msg.timestamp });
      },
      stdout: (msg) => {
        addLog({ type: 'stdout', data: msg.data, timestamp: msg.timestamp });
      },
      stderr: (msg) => {
        addLog({ type: 'stderr', data: msg.data, timestamp: msg.timestamp });
      },
      info: (msg) => {
        addLog({ type: 'info', data: msg.data, timestamp: msg.timestamp });
      },
      completed: (msg) => {
        setStatus('completed');
        setExitCode(msg.exit_code);
        setDuration(msg.duration_seconds);
        setIsConnected(false);

        const statusText = msg.exit_code === 0 ? 'successfully' : 'with errors';
        addLog({
          type: 'info',
          data: `Execution completed ${statusText} (exit code: ${msg.exit_code}, duration: ${msg.duration_seconds}s)`,
          timestamp: msg.timestamp
        });
      },
      error: (msg) => {
        setStatus('error');
        setIsConnected(false);
        addLog({ type: 'error', data: msg.data || msg.message, timestamp: msg.timestamp });
      }
    });

    sseClientRef.current = sseClient;

    const outputTopic = execution?.kafka?.output_topic;
    if (outputTopic) {
      console.log('Kafka subscription details:', {
        executionId: execution.id,
        outputTopic: execution.kafka?.output_topic,
        fromBeginning: true
      });

      const kafkaClient = new KafkaSSEClient(
        outputTopic,
        {
          connected: () => setIsKafkaConnected(true),
          kafka_started: () => {
            addKafkaMessage({
              type: 'info',
              data: `Subscribed to Kafka topic: ${outputTopic}`,
              timestamp: new Date().toISOString()
            });
          },
          kafka_message: (msg) => {
            addKafkaMessage({ type: 'kafka', data: msg.data, timestamp: msg.timestamp });
          },
          kafka_error: (msg) => {
            addKafkaMessage({ type: 'error', data: msg.data || msg.message, timestamp: msg.timestamp });
          },
          kafka_closed: () => {
            setIsKafkaConnected(false);
          }
        },
        { fromBeginning: true }
      );

      kafkaClientRef.current = kafkaClient;
    }

    // Cleanup on unmount
    return () => {
      if (sseClientRef.current) {
        sseClientRef.current.close();
      }
      if (kafkaClientRef.current) {
        kafkaClientRef.current.close();
      }
    };
  }, [execution]);

  const addLog = (logEntry) => {
    setLogs(prev => [...prev, logEntry]);
  };

  const addKafkaMessage = (message) => {
    setKafkaMessages(prev => [...prev, message]);
  };

  const handleStop = async () => {
    if (!execution || !execution.execution_id) return;

    try {
      await backendClient.stopExecution(execution.execution_id);
      setStatus('stopped');
      addLog({ type: 'info', data: 'Execution stopped by user', timestamp: new Date().toISOString() });
    } catch (error) {
      console.error('Failed to stop execution:', error);
      addLog({ type: 'error', data: `Failed to stop execution: ${error.message}`, timestamp: new Date().toISOString() });
    }
  };

  const handleDownloadLogs = async () => {
    if (!execution || !execution.execution_id) return;

    try {
      const response = await backendClient.getExecutionLogs(execution.execution_id);
      const blob = new Blob([response.logs], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${execution.execution_id}.log`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to download logs:', error);
      alert(`Failed to download logs: ${error.message}`);
    }
  };

  // Parse raw kafka message strings into objects for LatencyCharts
  const parsedKafkaMessages = useMemo(() => {
    return kafkaMessages
      .filter(m => m.type === 'kafka' && m.data)
      .map(m => { try { return JSON.parse(m.data); } catch { return null; } })
      .filter(Boolean);
  }, [kafkaMessages]);

  const getStatusColor = () => {
    if (status === 'completed' && exitCode === 0) return '#4ade80'; // green
    if (status === 'completed' || status === 'error') return '#ef4444'; // red
    if (status === 'running') return '#fbbf24'; // yellow
    return '#94a3b8'; // gray
  };

  if (isMinimized) {
    return (
      <div className="results-panel-minimized">
        <div className="minimized-header" onClick={() => setIsMinimized(false)}>
          <span className="status-indicator" style={{ backgroundColor: getStatusColor() }}></span>
          <span>Execution: {execution?.execution_id || 'Unknown'}</span>
          <span className="status-text">{status}</span>
          <button onClick={(e) => { e.stopPropagation(); onClose(); }} className="close-btn">×</button>
        </div>
      </div>
    );
  }

  return (
    <div className="results-panel" style={{ height: panelHeight }}>
      <div className="resize-handle" onMouseDown={handleMouseDown} />
      <div className="results-header">
        <div className="header-left">
          <span className="status-indicator" style={{ backgroundColor: getStatusColor() }}></span>
          <h3>Execution: {execution?.execution_id || 'Unknown'}</h3>
        </div>
        <div className="header-right">
          <span className="status-text">{status}</span>
          {duration && <span className="duration-text">{duration}s</span>}
          {isConnected && <span className="connected-indicator">● Connected</span>}
          <button onClick={() => setIsMinimized(true)} className="minimize-btn" title="Minimize">−</button>
          <button onClick={onClose} className="close-btn" title="Close">×</button>
        </div>
      </div>

      <div className="results-body">
        <div className="results-tabs">
          <button
            className={`tab-btn ${activeView === 'logs' ? 'active' : ''}`}
            onClick={() => setActiveView('logs')}
            type="button"
          >
            Logs
          </button>
          <button
            className={`tab-btn ${activeView === 'kafka' ? 'active' : ''}`}
            onClick={() => setActiveView('kafka')}
            type="button"
            disabled={!execution?.kafka?.output_topic}
            title={execution?.kafka?.output_topic ? `Topic: ${execution.kafka.output_topic}` : 'No Kafka sink detected in script'}
          >
            Kafka {isKafkaConnected ? '●' : ''}
          </button>
          <button
            className={`tab-btn ${activeView === 'charts' ? 'active' : ''}`}
            onClick={() => setActiveView('charts')}
            type="button"
            disabled={kafkaMessages.length === 0}
            title="Latency charts"
          >
            Charts
          </button>
        </div>

        {activeView === 'logs' && (
          <div className="logs-container">
            {logs.length === 0 && (
              <div className="no-logs">Waiting for output...</div>
            )}
            {logs.map((log, index) => (
              <div key={index} className={`log-line log-${log.type}`}>
                <span className="log-timestamp">
                  {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ''}
                </span>
                <span className="log-data">{log.data}</span>
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        )}

        {activeView === 'kafka' && (
          <div className="logs-container">
            {!execution?.kafka?.output_topic && (
              <div className="no-logs">No Kafka sink detected in generated script.</div>
            )}
            {execution?.kafka?.output_topic && kafkaMessages.length === 0 && (
              <div className="no-logs">Waiting for Kafka messages...</div>
            )}
            {kafkaMessages.map((msg, index) => (
              <div key={index} className={`log-line log-${msg.type}`}>
                <span className="log-timestamp">
                  {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : ''}
                </span>
                <span className="log-data">{msg.data}</span>
              </div>
            ))}
            <div ref={kafkaEndRef} />
          </div>
        )}

        {activeView === 'charts' && (
          <LatencyCharts kafkaMessages={parsedKafkaMessages} startTime={startTime} />
        )}
      </div>

      <div className="results-footer">
        {isConnected && status === 'running' && (
          <button onClick={handleStop} className="btn-stop">Stop Execution</button>
        )}
        <button onClick={handleDownloadLogs} className="btn-download">Download Logs</button>
        <div className="footer-info">
          {exitCode !== null && (
            <span className={`exit-code ${exitCode === 0 ? 'success' : 'error'}`}>
              Exit Code: {exitCode}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
