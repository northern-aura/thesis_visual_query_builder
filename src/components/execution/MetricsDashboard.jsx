import React, { useState, useRef, useCallback, useEffect } from 'react';
import { generateDirectPython } from '../../helpers/export/directPythonExport';
import { backendClient } from '../../services/backendClient';
import { KafkaSSEClient } from '../../services/kafkaSseClient';
import { ExecutionSSEClient } from '../../services/sseClient';
import { queryGroups } from '../queries-list/queries';
import { nodeTypes } from '../nodes/defaultNodes.ts';
import LatencyCharts from './LatencyCharts';
import { buildChartSummary } from '../../helpers/execution/chartStats';
import './MetricsDashboard.css';

// Time (ms) to wait for pipeline to initialise before marking it ready for frames.
// Flink's KafkaSource takes ~25–30s to become a ready consumer; firing the sender before
// that means the first chunk of frames piles up in the topic and inflates backpressure.
const PIPELINE_INIT_DELAY_MS = 30000;

// Fallback quiet-period (only used when we can't parse the sent-frame count from sender
// stdout). The primary "done" signal is output_count >= sent_count, not inactivity.
const QUIET_DRAIN_MS = 120000;

// Hard ceiling so a truly stuck pipeline can't hang the queue forever. Slow VLMs can take
// ~1-2s per frame → 3953 frames ≈ 60-130min, so keep this generous.
const MAX_POST_SENDER_WAIT_MS = 3 * 60 * 60 * 1000; // 3 h

// Small settle delay between queued runs so the backend marks the prior pipeline stopped
// before the next /api/execute call checks is_busy().
const INTER_RUN_SETTLE_MS = 2000;

// Reconstruct nodes the same way loadPresetQuery does in App.jsx
// Uses prefixed IDs (db_) to avoid DOM collisions with canvas nodes
function buildNodesAndEdges(query, groupId) {
    const sorted = sortByNext(query.nodes);
    const pfx = 'db_';
    const nodes = sorted.map((node, i) => {
        const label = node.type === 'start' ? 'Kafka Source'
            : node.type === 'end' ? 'Kafka Sink'
            : convertLabel(node.type);
        const nodeDefinition = nodeTypes.find(n => n.label.toLowerCase() === label.toLowerCase());
        const params = { ...(node.params || {}) };
        if (node.type === 'start' && groupId) {
            params.group_id = groupId;
        }
        return {
            ...node,
            id: pfx + node.id,
            position: { x: i * 200, y: 100 },
            data: { label, nodeType: node.type, nodeDefinition },
            type: (node.type === 'start' || node.type === 'end') ? node.type : 'function',
            params
        };
    });

    const edges = query.nodes
        .filter(n => n.nextNode)
        .map(n => ({
            id: `e-${pfx}${n.id}-${pfx}${n.nextNode}`,
            source: pfx + n.id,
            target: pfx + n.nextNode
        }));

    return { nodes, edges };
}

function convertLabel(str) {
    if (str.includes('_')) {
        return str.split('_').map(word => {
            if (['cv', 'llm', 'id'].includes(word.toLowerCase())) return word.toUpperCase();
            return word.charAt(0).toUpperCase() + word.slice(1);
        }).join(' ');
    }
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function sortByNext(nodes) {
    const map = new Map(nodes.map(n => [n.id, n]));
    const start = nodes.find(n => n.type === 'start');
    if (!start) return nodes;
    const out = [];
    const seen = new Set();
    let cur = start;
    while (cur && !seen.has(cur.id)) {
        out.push(cur);
        seen.add(cur.id);
        cur = cur.nextNode ? map.get(cur.nextNode) : null;
    }
    return out;
}

function getOutputTopic(query) {
    const sink = query.nodes.find(n => n.type === 'end');
    return sink?.params?.topic || null;
}

const delay = ms => new Promise(r => setTimeout(r, ms));

// Parse sender stdout_tail to recover total sent frames.
// Supports both:
// - cars sender: "Sending frame N"
// - volleyball sender: "Done. X frames sent to <topic>."
function parseSentFrameCount(stdout) {
    if (!stdout) return null;

    // Prefer explicit final summary if available.
    const doneMatch = stdout.match(/Done\.\s*(\d+)\s+frames\s+sent\b/i);
    if (doneMatch) {
        const total = parseInt(doneMatch[1], 10);
        if (Number.isFinite(total) && total >= 0) return total;
    }

    // Fallback: infer from largest 0-indexed frame id used by cars sender logs.
    let max = -1;
    const re = /Sending frame (\d+)/g;
    let m;
    while ((m = re.exec(stdout)) !== null) {
        const n = parseInt(m[1], 10);
        if (Number.isFinite(n) && n > max) max = n;
    }
    return max < 0 ? null : max + 1;
}

function parseWindowFrameSize(query) {
    const win = query.nodes.find(n => n.type === 'window');
    const rawSize = win?.params?.window_size;
    if (rawSize == null) return null;
    const match = String(rawSize).match(/(\d+)/);
    if (!match) return null;
    const size = parseInt(match[1], 10);
    return Number.isFinite(size) && size > 0 ? size : null;
}

function buildDrainTarget(query, sentFrames) {
    if (sentFrames == null) {
        return {
            inputFrames: null,
            brokerMessages: null,
            processedFrames: null,
            isWindowed: false,
            trailingFrames: 0,
            label: null
        };
    }

    const windowSize = parseWindowFrameSize(query);
    if (windowSize) {
        const fullWindows = Math.floor(sentFrames / windowSize);
        const trailingFrames = sentFrames % windowSize;
        if (fullWindows > 0) {
            return {
                inputFrames: sentFrames,
                brokerMessages: fullWindows,
                processedFrames: fullWindows * windowSize,
                isWindowed: true,
                windowSize,
                trailingFrames,
                label: `${fullWindows} windows / ${fullWindows * windowSize} represented frames`
            };
        }
    }

    return {
        inputFrames: sentFrames,
        brokerMessages: sentFrames,
        processedFrames: sentFrames,
        isWindowed: false,
        trailingFrames: 0,
        label: `${sentFrames} messages`
    };
}

function slugify(title) {
    return title.replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_|_$/g, '').toLowerCase();
}

function extractQueryMeta(query) {
    const nodes = query.nodes;
    const llmN = nodes.find(n => n.type === 'llm');
    const resizeN = nodes.find(n => n.type === 'resize');
    const pipelineNodes = sortByNext(nodes)
        .map(n => n.type === 'start' ? 'Source' : n.type === 'end' ? 'Sink' : convertLabel(n.type))
        .join(' -> ');

    return {
        llm_model: llmN?.subtype || llmN?.params?.subtype || '',
        has_window: nodes.some(n => n.type === 'window'),
        has_grayscale: nodes.some(n => n.type === 'grayscale'),
        resize_width: resizeN?.params?.width || '',
        resize_height: resizeN?.params?.height || '',
        pipeline_nodes: pipelineNodes
    };
}

export default function MetricsDashboard({ onClose, customNodes = [] }) {
    const [queryResults, setQueryResults] = useState({});
    const [activeQuery, setActiveQuery] = useState(null);
    const [runningQuery, setRunningQuery] = useState(null);
    const [resultsTab, setResultsTab] = useState('console');
    const kafkaClientsRef = useRef({});
    const sseClientsRef = useRef({});
    const abortRef = useRef(false);
    const activeExecIds = useRef([]);
    const kafkaEndRef = useRef(null);
    const queryResultsRef = useRef({});
    const onKafkaMessageRef = useRef(null);
    const onPipelineDoneRef = useRef(null);
    const [consoleLines, setConsoleLines] = useState([]);
    const [chartVersion, setChartVersion] = useState(0);
    const rafPendingRef = useRef(false);
    const [selected, setSelected] = useState(() => new Set());
    const [queueRunning, setQueueRunning] = useState(false);
    const abortQueueRef = useRef(false);

    const addConsoleLine = useCallback((type, data) => {
        setConsoleLines(prev => [...prev, { type, data, timestamp: new Date().toISOString() }]);
    }, []);

    const updateResult = useCallback((title, updates) => {
        setQueryResults(prev => ({
            ...prev,
            [title]: { ...(prev[title] || {}), ...updates }
        }));
    }, []);

    // Auto-scroll kafka console
    useEffect(() => {
        kafkaEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [consoleLines]);

    const runSingleQuery = useCallback(async (query, options = {}) => {
        const { autoSender = false, continuousConsumption = false, stopOnSenderExit = false } = options;
        if (runningQuery) return;

        const querySlug = slugify(query.title);
        const groupId = `dashboard_${Date.now()}_0`;

        setRunningQuery(query.title);
        setActiveQuery(query.title);
        abortRef.current = false;
        activeExecIds.current = [];
        setConsoleLines([]);

        updateResult(query.title, {
            status: 'starting pipeline...',
            kafkaMessages: [],
            aggregateMetrics: null,
            duration: null,
            errorMsg: null,
            savedPath: null
        });

        addConsoleLine('info', `Starting pipeline: ${query.title}`);
        queryResultsRef.current[query.title] = { kafkaMessages: [], aggregateMetrics: {} };
        // Clear previous results file so this run starts fresh
        const resultsFile = `${querySlug}.jsonl`;
        backendClient.appendResult(resultsFile, '', true);

        const queryStartTime = Date.now();

        try {
            // 1. Build pipeline
            const { nodes, edges } = buildNodesAndEdges(query, groupId);
            const pythonCode = generateDirectPython(nodes, edges, query.title, customNodes);
            const outputTopic = getOutputTopic(query);

            // 1b. Clear input topic so pipeline only sees fresh video frames
            const inputTopic = query.nodes.find(n => n.type === 'start')?.params?.topic;
            if (inputTopic) {
                addConsoleLine('info', `Clearing input topic: ${inputTopic}`);
                await backendClient.clearTopic(inputTopic).catch(err =>
                    addConsoleLine('warn', `Could not clear input topic: ${err.message}`)
                );
            }
            if (outputTopic && outputTopic !== inputTopic) {
                addConsoleLine('info', `Clearing output topic: ${outputTopic}`);
                await backendClient.clearTopic(outputTopic).catch(err =>
                    addConsoleLine('warn', `Could not clear output topic: ${err.message}`)
                );
            }

            // 2. Start Flink pipeline
            const pipelineResult = await backendClient.executeScript(
                `${querySlug}.py`, pythonCode, query.title
            );
            const pipelineExecId = pipelineResult.execution_id;
            activeExecIds.current.push(pipelineExecId);
            addConsoleLine('info', `Pipeline submitted (${pipelineExecId})`);

            // Monitor pipeline SSE for early errors + detect external termination
            let pipelineError = null;
            let pipelineDone = false;
            const pipelineSse = new ExecutionSSEClient(pipelineExecId, {
                connected: () => {},
                started: () => {},
                docker_status: () => {},
                // Surface pipeline logs so the user can see why it exits unexpectedly.
                // (Previously suppressed → "Pipeline terminated. Collected 0 messages" with
                // no visible reason.)
                stdout: (msg) => {
                    const line = (msg.data || '').trimEnd();
                    if (line) addConsoleLine('pipeline', line);
                },
                stderr: (msg) => {
                    const line = (msg.data || '').trimEnd();
                    if (line) addConsoleLine('pipeline-err', line);
                },
                info: (msg) => {
                    const line = (msg.data || msg.message || '').trimEnd();
                    if (line) addConsoleLine('info', `[pipeline] ${line}`);
                },
                completed: (msg) => {
                    pipelineDone = true;
                    const code = msg?.exit_code ?? msg?.data?.exit_code ?? msg?.returncode;
                    addConsoleLine(code === 0 ? 'info' : 'error',
                        `[pipeline] process exited${code != null ? ` (code ${code})` : ''}`);
                    onPipelineDoneRef.current?.();
                },
                error: (msg) => {
                    pipelineError = msg.data || msg.message || 'Pipeline error';
                    pipelineDone = true;
                    addConsoleLine('error', `[pipeline] ${pipelineError}`);
                    onPipelineDoneRef.current?.();
                }
            });
            sseClientsRef.current[query.title] = pipelineSse;

            // 3. Wait for pipeline init
            updateResult(query.title, { status: 'waiting for pipeline init...' });
            addConsoleLine('info', `Waiting ${PIPELINE_INIT_DELAY_MS / 1000}s for pipeline init...`);
            await delay(PIPELINE_INIT_DELAY_MS);
            if (pipelineError) throw new Error(pipelineError);
            if (abortRef.current) throw new Error('Aborted');

            // 4. Subscribe to Kafka output topic
            if (outputTopic) {
                addConsoleLine('info', `Subscribing to Kafka topic: ${outputTopic}`);
                const kafkaClient = new KafkaSSEClient(outputTopic, {
                    connected: () => {},
                    kafka_started: () => {},
                    kafka_message: (msg) => {
                        try {
                            const data = JSON.parse(msg.data);
                            // Track in ref for reliable save access
                            const refEntry = queryResultsRef.current[query.title] || { kafkaMessages: [], aggregateMetrics: {} };
                            refEntry.kafkaMessages.push(data);
                            const metricsArr = refEntry.kafkaMessages.filter(m => m.metrics).map(m => m.metrics);
                            refEntry.aggregateMetrics = aggregateMetrics(metricsArr);
                            queryResultsRef.current[query.title] = refEntry;
                            // Coalesce UI updates to one per animation frame
                            if (!rafPendingRef.current) {
                                rafPendingRef.current = true;
                                requestAnimationFrame(() => {
                                    rafPendingRef.current = false;
                                    setQueryResults(prev => ({
                                        ...prev,
                                        [query.title]: { ...queryResultsRef.current[query.title] }
                                    }));
                                    setChartVersion(v => v + 1);
                                });
                            }
                            // Add to console display
                            addConsoleLine('kafka', msg.data);
                            // Notify completion checker
                            onKafkaMessageRef.current?.();
                        } catch (e) {
                            addConsoleLine('kafka', msg.data || String(e));
                        }
                        // Write to disk in real-time (outside try — must not block message processing)
                        try { backendClient.appendResult(resultsFile, msg.data); } catch { void 0; }
                    },
                    kafka_error: (msg) => {
                        addConsoleLine('error', msg.data || 'Kafka error');
                    },
                    kafka_closed: () => {}
                }, { fromBeginning: false });
                kafkaClientsRef.current[query.title] = kafkaClient;
            }

            // 5. Fire the sender — automatically if autoSender is set and the query has a sender script,
            //    otherwise instruct the user to run it manually and hit "Finish & Save Report".
            const senderScript = query.senderScript;
            if (autoSender && senderScript) {
                updateResult(query.title, { status: continuousConsumption ? 'live streaming...' : 'auto-sender running...' });
                addConsoleLine('info', `${continuousConsumption ? 'Auto-running sender (live mode)' : 'Auto-running sender'}: ${senderScript}`);
                if (continuousConsumption) {
                    addConsoleLine(
                        'info',
                        stopOnSenderExit
                            ? 'Continuous mode enabled: results stream live; after sender exits we wait for the pipeline to finish processing all frames before ending.'
                            : 'Continuous mode enabled: results stream live. Click "Finish & Save Report" to stop.'
                    );
                }
                // Don't block the promise here — the sender run is awaited inside the
                // wait-for-results block below so that Kafka messages keep flowing into the UI.
            } else if (autoSender && !senderScript) {
                updateResult(query.title, { status: 'awaiting frames (no sender configured)...' });
                addConsoleLine('warn', 'Auto-sender requested but this query has no senderScript. Start the sender manually.');
            } else {
                updateResult(query.title, { status: 'awaiting frames...' });
                addConsoleLine('info', 'Pipeline ready. Start your video sender (e.g. send_video.py) now. Click "Finish & Save Report" when done.');
            }

            // 6. Wait for all results (event-driven — no setInterval polling)
            if (outputTopic) {
                await new Promise((resolve) => {
                    let resolved = false;
                    let abortPoll = null;
                    const finish = (reason) => {
                        if (resolved) return;
                        resolved = true;
                        if (abortPoll) clearInterval(abortPoll);
                        addConsoleLine('info', reason);
                        resolve();
                    };

                    // Called after each Kafka message — only updates status counter.
                    // Completion is user-driven via the "Finish & Save Report" button.
                    const checkCompletion = () => {
                        const count = queryResultsRef.current[query.title]?.kafkaMessages?.length || 0;
                        updateResult(query.title, {
                            status: `processing... ${count} messages`
                        });
                    };

                    // Hook into existing handlers via refs
                    onKafkaMessageRef.current = checkCompletion;
                    onPipelineDoneRef.current = () => {
                        const count = queryResultsRef.current[query.title]?.kafkaMessages?.length || 0;
                        finish(`Pipeline terminated. Collected ${count} messages.`);
                    };

                    // If pipeline already done before we got here
                    if (pipelineDone) {
                        const count = queryResultsRef.current[query.title]?.kafkaMessages?.length || 0;
                        finish(`Pipeline already terminated. Collected ${count} messages.`);
                        return;
                    }

                    // Auto-sender path: fire the sender, parse the total frame count it sent
                    // from stdout, then wait until `output_count >= sent_count` so filtered
                    // queries don't stop prematurely on a temporary LLM gap. Falls back to a
                    // quiet-period drain only when we couldn't parse the sender tail. A long
                    // "no-progress" guard (see STALL_LIMIT_MS below) still bounds filtered
                    // queries where output count will never reach sent count.
                    if (autoSender && senderScript) {
                        // Drain after sender exits whenever we're not in pure-live mode.
                        // pure-live = continuousConsumption && !stopOnSenderExit → user must click Finish.
                        // Otherwise: wait for the output topic to receive all expected frames before finishing.
                        const shouldDrainOnSenderExit = !continuousConsumption || stopOnSenderExit;

                        backendClient.runSender({ script: senderScript })
                            .then(async (r) => {
                                if (r.stdout_tail?.trim()) addConsoleLine('info', `[sender stdout]\n${r.stdout_tail.trim()}`);
                                if (r.stderr_tail?.trim()) addConsoleLine('warn', `[sender stderr]\n${r.stderr_tail.trim()}`);

                                if (!shouldDrainOnSenderExit) {
                                    addConsoleLine(
                                        r.returncode === 0 ? 'info' : 'warn',
                                        `Sender exited${r.returncode != null ? ` (code ${r.returncode})` : ''}. ` +
                                        `Live pipeline remains active until you finish.`
                                    );
                                    return;
                                }

                                const sentFrames = parseSentFrameCount(r.stdout_tail);
                                const drainTarget = buildDrainTarget(query, sentFrames);
                                const target = drainTarget.brokerMessages;
                                addConsoleLine(r.returncode === 0 ? 'info' : 'warn',
                                    `Sender exited (code ${r.returncode}, ${r.duration_s}s).` +
                                    (target != null
                                        ? ` Waiting for pipeline to process all ${target} frames…`
                                        : ` Could not parse frame count — falling back to quiet-period drain (${QUIET_DRAIN_MS / 1000}s).`));

                                if (drainTarget.isWindowed && drainTarget.trailingFrames > 0) {
                                    addConsoleLine('warn',
                                        `Windowed query caveat: ${drainTarget.inputFrames} sent frames with ${drainTarget.windowSize}-frame windows ` +
                                        `creates ${drainTarget.brokerMessages} full windows (${drainTarget.processedFrames} frames). ` +
                                        `${drainTarget.trailingFrames} trailing frame(s) stay buffered unless the window operator flushes partial windows.`);
                                }

                                // Filtered queries (skip_frames, filter_empty, etc.) drop frames,
                                // so broker_offset may never reach target. Bail if the output
                                // topic stops growing for STALL_LIMIT_MS.
                                const STALL_LIMIT_MS = 5 * 60 * 1000; // 5 min
                                const drainStart = Date.now();
                                let lastLogAt = 0;
                                let lastBrokerOffset = -1;
                                let lastBrokerMoveAt = Date.now();
                                while (!resolved) {
                                    if (abortRef.current) {
                                        const count = queryResultsRef.current[query.title]?.kafkaMessages?.length || 0;
                                        finish(`Aborted during drain. Collected ${count} messages.`);
                                        return;
                                    }
                                    const now = Date.now();
                                    const waited = now - drainStart;
                                    const messages = queryResultsRef.current[query.title]?.kafkaMessages || [];
                                    const count = messages.length;

                                    // Broker-authoritative count of messages on the output topic.
                                    // Independent of our SSE subscription, so it's correct even
                                    // when the SSE flaps/reconnects and drops messages.
                                    let brokerOffset = null;
                                    if (outputTopic) {
                                        try {
                                            const r = await backendClient.getTopicOffset(outputTopic);
                                            brokerOffset = r?.total ?? null;
                                        } catch { /* ignore; retry next tick */ }
                                    }
                                    if (brokerOffset != null && brokerOffset !== lastBrokerOffset) {
                                        lastBrokerOffset = brokerOffset;
                                        lastBrokerMoveAt = now;
                                    }
                                    const sinceBrokerMove = now - lastBrokerMoveAt;

                                    // Primary stop: broker has all expected output messages/windows.
                                    if (target != null && brokerOffset != null && brokerOffset >= target) {
                                        addConsoleLine('info',
                                            `Output topic reached ${brokerOffset}/${target} — all frames written to Kafka.`);
                                        // Wait a brief extra tick so any in-flight SSE messages land in the UI cache.
                                        await delay(2000);
                                        break;
                                    }

                                    // Fallback stop when we don't know target: output topic silent long enough.
                                    if (target == null && brokerOffset != null && sinceBrokerMove >= QUIET_DRAIN_MS) {
                                        addConsoleLine('warn',
                                            `Output topic idle ${Math.round(sinceBrokerMove / 1000)}s at ${brokerOffset} msgs — finishing.`);
                                        break;
                                    }

                                    // Filtered-query guard: target is known but unreachable.
                                    if (target != null && brokerOffset != null && sinceBrokerMove >= STALL_LIMIT_MS) {
                                        addConsoleLine('warn',
                                            `Output topic idle ${Math.round(sinceBrokerMove / 60000)}min at ${brokerOffset}/${target} — ` +
                                            `pipeline likely done filtering.`);
                                        break;
                                    }

                                    if (waited >= MAX_POST_SENDER_WAIT_MS) {
                                        addConsoleLine('warn',
                                            `Drain cap hit (${MAX_POST_SENDER_WAIT_MS / 60000}min). ` +
                                            `broker=${brokerOffset ?? '?'} sse=${count}${target != null ? '/' + target : ''}. Finishing.`);
                                        break;
                                    }

                                    // Progress log every 10s
                                    if (now - lastLogAt >= 10000) {
                                        addConsoleLine('info',
                                            `Draining… broker=${brokerOffset ?? '?'} sse=${count}` +
                                            `${target != null ? '/' + target : ''} (${Math.round(waited / 1000)}s elapsed).`);
                                        lastLogAt = now;
                                    }
                                    await delay(2000);
                                }
                                const count = queryResultsRef.current[query.title]?.kafkaMessages?.length || 0;
                                finish(`Auto-sender finished. Broker=${lastBrokerOffset >= 0 ? lastBrokerOffset : '?'}, SSE collected ${count}${target != null ? '/' + target : ''} messages.`);
                            })
                            .catch((e) => {
                                addConsoleLine('error', `Sender error: ${e.message}`);
                                if (shouldDrainOnSenderExit) {
                                    const count = queryResultsRef.current[query.title]?.kafkaMessages?.length || 0;
                                    finish(`Sender failed. Collected ${count} messages.`);
                                }
                            });
                    }

                    // Manual/abort path: run continues until the user clicks "Finish & Save Report"
                    // (which sets abortRef.current = true) or the pipeline itself terminates.
                    abortPoll = setInterval(() => {
                        if (abortRef.current) {
                            const count = queryResultsRef.current[query.title]?.kafkaMessages?.length || 0;
                            finish(`Finished by user. Collected ${count} messages.`);
                        }
                    }, 500);
                });

                // Clear hooks
                onKafkaMessageRef.current = null;
                onPipelineDoneRef.current = null;
            }

            // 7. Stop the pipeline
            await backendClient.stopExecution(pipelineExecId).catch(() => {});

            const totalDuration = (Date.now() - queryStartTime) / 1000;
            updateResult(query.title, { status: 'completed', duration: totalDuration });
            addConsoleLine('info', `Completed in ${totalDuration.toFixed(1)}s`);

        } catch (error) {
            updateResult(query.title, { status: 'error', errorMsg: error.message });
            addConsoleLine('error', `Error: ${error.message}`);
        } finally {
            // Cleanup SSE/Kafka clients
            sseClientsRef.current[query.title]?.close?.();
            kafkaClientsRef.current[query.title]?.close?.();

            // Data already written to disk in real-time via appendResult
            const msgCount = queryResultsRef.current[query.title]?.kafkaMessages?.length || 0;
            const totalDuration = (Date.now() - queryStartTime) / 1000;
            addConsoleLine('info', `Done. ${msgCount} messages written to results/${resultsFile} (${totalDuration.toFixed(1)}s)`);

            // Persist metrics snapshot (summary + chart-ready data) for thesis use
            try {
                const kafkaMessages = queryResultsRef.current[query.title]?.kafkaMessages || [];
                const aggregateMetricsRef = queryResultsRef.current[query.title]?.aggregateMetrics || {};
                const chartSummary = buildChartSummary(kafkaMessages);
                const meta = extractQueryMeta(query);
                const ts = new Date().toISOString();
                const accMeans = chartSummary?.accuracy_means_pct || {};
                const ops = chartSummary?.box_stats?.operators || {};
                const opMean = (name) => ops[name]?.mean ?? null;

                const csvRow = {
                    query_title: query.title,
                    timestamp: ts,
                    duration_s: totalDuration.toFixed(2),
                    message_count: msgCount,
                    llm_model: meta.llm_model,
                    has_window: meta.has_window,
                    has_grayscale: meta.has_grayscale,
                    resize_width: meta.resize_width,
                    resize_height: meta.resize_height,
                    brand_accuracy: accMeans.brand_match ?? accMeans.brand_accuracy ?? accMeans.brand ?? '',
                    color_accuracy: accMeans.color_match ?? accMeans.color_accuracy ?? accMeans.color ?? '',
                    plate_accuracy: accMeans.plate_match ?? accMeans.plate_accuracy ?? accMeans.plate ?? '',
                    action_accuracy: accMeans.action_match ?? accMeans.action_match_accuracy ?? '',
                    action_recall_micro: aggregateMetricsRef.actionRecallMicro ?? '',
                    avg_llm_time_ms: chartSummary?.box_stats?.llm?.mean ?? '',
                    avg_e2e_ms: chartSummary?.box_stats?.e2e?.mean ?? '',
                    avg_decode_ms: opMean('decode'),
                    avg_resize_ms: opMean('resize'),
                    avg_llm_op_ms: opMean('llm'),
                    avg_grayscale_ms: opMean('grayscale'),
                    pipeline_nodes: meta.pipeline_nodes
                };

                const detailData = {
                    query_title: query.title,
                    slug: querySlug,
                    timestamp: ts,
                    duration_s: totalDuration,
                    message_count: msgCount,
                    results_file: `results/${resultsFile}`,
                    query_meta: meta,
                    aggregate_metrics: aggregateMetricsRef,
                    chart_summary: chartSummary
                };

                await backendClient.saveMetrics(querySlug, csvRow, detailData);
                addConsoleLine('info', `Metrics saved to results/metrics/${querySlug}.json and results/metrics/summary.csv`);
                updateResult(query.title, {
                    savedPath: `results/${resultsFile}`,
                    metricsPath: `results/metrics/${querySlug}.json`
                });

                try {
                    const plotsRes = await backendClient.renderPlots(querySlug);
                    addConsoleLine('info', `Plots saved to ${plotsRes.outputDir}/`);
                    updateResult(query.title, { plotsPath: plotsRes.outputDir });
                } catch (plotErr) {
                    addConsoleLine('warn', `Could not render plots: ${plotErr.message}`);
                }
            } catch (saveErr) {
                addConsoleLine('warn', `Could not save metrics: ${saveErr.message}`);
                updateResult(query.title, { savedPath: `results/${resultsFile}` });
            }

            // Reset per-run refs so stale callbacks / handles from this run can't
            // fire during the next one. Fixes the "must close & reopen the tab
            // between queries" bug.
            onKafkaMessageRef.current = null;
            onPipelineDoneRef.current = null;
            sseClientsRef.current = {};
            kafkaClientsRef.current = {};
            rafPendingRef.current = false;
            abortRef.current = false;
            activeExecIds.current = [];

            // Settle: give the backend a moment to mark the pipeline stopped so
            // the next /api/execute call doesn't hit is_busy().
            await delay(INTER_RUN_SETTLE_MS);

            setRunningQuery(null);
        }
    }, [runningQuery, customNodes, updateResult, addConsoleLine]);

    const handleStop = useCallback(async () => {
        abortRef.current = true;
        onPipelineDoneRef.current?.(); // Trigger completion to save metrics
        Object.values(sseClientsRef.current).forEach(c => c?.close?.());
        Object.values(kafkaClientsRef.current).forEach(c => c?.close?.());
        for (const execId of activeExecIds.current) {
            await backendClient.stopExecution(execId).catch(() => {});
        }
        activeExecIds.current = [];
        if (runningQuery) {
            updateResult(runningQuery, { status: 'finishing' });
            addConsoleLine('info', 'Finished by user — saving report…');
        }
        setRunningQuery(null);
    }, [runningQuery, updateResult, addConsoleLine]);

    const handleSelectQuery = useCallback((title) => {
        setActiveQuery(title);
        // If viewing a completed query's past results, show them in console
        if (title !== runningQuery) {
            const result = queryResults[title];
            if (result?.kafkaMessages?.length) {
                const lines = [
                    { type: 'info', data: `Showing saved results for: ${title}`, timestamp: new Date().toISOString() }
                ];
                result.kafkaMessages.forEach(msg => {
                    let content;
                    try { content = typeof msg === 'string' ? msg : JSON.stringify(msg); } catch { content = String(msg); }
                    lines.push({ type: 'kafka', data: content, timestamp: new Date().toISOString() });
                });
                if (result.duration) {
                    lines.push({ type: 'info', data: `Completed in ${result.duration.toFixed(1)}s - ${result.kafkaMessages.length} messages`, timestamp: new Date().toISOString() });
                }
                if (result.savedPath) {
                    lines.push({ type: 'info', data: `Results saved to ${result.savedPath}`, timestamp: new Date().toISOString() });
                }
                setConsoleLines(lines);
            } else if (!result) {
                setConsoleLines([]);
            }
        }
    }, [runningQuery, queryResults]);

    // Flatten runnable queries and inherit each group's senderScript so the queue
    // runner knows which frame-sender to invoke per query.
    const allQueries = queryGroups
        .filter(g => g.runnable)
        .flatMap(g => g.queries.map(q => ({
            senderScript: g.senderScript,
            dataset: g.dataset,
            ...q
        })));

    const runSelected = useCallback(async () => {
        if (queueRunning || runningQuery) return;
        const queue = allQueries.filter(q => selected.has(q.title));
        if (queue.length === 0) return;
        abortQueueRef.current = false;
        setQueueRunning(true);
        try {
            for (const q of queue) {
                if (abortQueueRef.current) break;
                await runSingleQuery(q, { autoSender: true, continuousConsumption: true, stopOnSenderExit: true });
            }
        } finally {
            setQueueRunning(false);
        }
    // allQueries is recomputed each render from a static import; including selected + runSingleQuery is enough.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selected, queueRunning, runningQuery, runSingleQuery]);

    const toggleSelected = useCallback((title) => {
        setSelected(prev => {
            const n = new Set(prev);
            if (n.has(title)) n.delete(title); else n.add(title);
            return n;
        });
    }, []);

    const selectAll = useCallback(() => {
        setSelected(new Set(allQueries.map(q => q.title)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const clearSelection = useCallback(() => setSelected(new Set()), []);

    const stopQueue = useCallback(() => {
        abortQueueRef.current = true;
        // handleStop also ends the currently running query so the loop can advance/exit.
        handleStop();
    }, [handleStop]);
    const activeResult = activeQuery ? (queryResults[activeQuery] || {}) : {};
    const activeMetrics = activeResult.aggregateMetrics || {};

    return (
        <div className="metrics-dashboard">
            <div className="metrics-header">
                <h3>Query Runner</h3>
                <button onClick={onClose} className="close-btn" title="Close">x</button>
            </div>

            <div className="metrics-body">
                <div className="query-list">
                    <div className="query-list-toolbar">
                        <button
                            className="btn-run-selected"
                            onClick={runSelected}
                            disabled={queueRunning || !!runningQuery || selected.size === 0}
                            title="Run every checked query in live mode, one after the other. Each run drains until the output topic has all frames (or stalls) before advancing."
                        >
                            Run Selected ({selected.size})
                        </button>
                        {queueRunning && (
                            <button className="btn-stop-queue" onClick={stopQueue} title="Stop the current run and cancel remaining queued queries">
                                Stop Queue
                            </button>
                        )}
                        <button className="btn-sel-aux" onClick={selectAll} disabled={queueRunning}>All</button>
                        <button className="btn-sel-aux" onClick={clearSelection} disabled={queueRunning}>None</button>
                    </div>
                    {allQueries.map(q => {
                        const r = queryResults[q.title] || {};
                        const isActive = activeQuery === q.title;
                        const isRunning = runningQuery === q.title;
                        const isChecked = selected.has(q.title);
                        const isBestOptimized = q.meta?.bestOptimized;
                        const isPinkVolleyball =
                            q.dataset?.includes('Volleyball') &&
                            (q.dataset.includes('Naive') || isBestOptimized);
                        const changedThisTurn = q.meta?.changedThisTurn;
                        const needsRun = q.meta?.needsRun;
                        return (
                            <div
                                key={q.title}
                                className={`query-card ${isActive ? 'selected' : ''} ${isPinkVolleyball ? 'query-card-volleyball-marked' : ''}`}
                                onClick={() => handleSelectQuery(q.title)}
                            >
                                <div className="query-card-header">
                                    <input
                                        type="checkbox"
                                        className="query-card-check"
                                        checked={isChecked}
                                        onClick={(e) => e.stopPropagation()}
                                        onChange={() => toggleSelected(q.title)}
                                        disabled={queueRunning || !!runningQuery}
                                        title={q.senderScript ? `Sender: ${q.senderScript}` : 'No sender configured — will run manually'}
                                    />
                                    <span className="query-title">
                                        <span className="query-title-text">{q.title}</span>
                                        {isBestOptimized && <span className="query-run-badge query-run-badge-best">best</span>}
                                        {needsRun && <span className="query-run-badge query-run-badge-run">to run</span>}
                                        {changedThisTurn && <span className="query-run-badge query-run-badge-updated">updated</span>}
                                    </span>
                                    <div className="query-card-actions">
                                        {r.status && r.status !== 'pending' && (
                                            <span className={`status-badge status-${getStatusClass(r.status)}`}>
                                                {r.status === 'completed' ? 'done' :
                                                 r.status === 'error' ? 'err' :
                                                 r.status === 'stopped' ? 'stop' :
                                                 'run'}
                                            </span>
                                        )}
                                        {isRunning ? (
                                            <button
                                                className="btn-finish-query"
                                                onClick={(e) => { e.stopPropagation(); handleStop(); }}
                                                title="End the run, save metrics, and render plots"
                                            >
                                                Finish & Save Report
                                            </button>
                                        ) : (
                                            <>
                                                <button
                                                    className="btn-run-query"
                                                    onClick={(e) => { e.stopPropagation(); runSingleQuery(q); }}
                                                    disabled={!!runningQuery}
                                                    title="Run pipeline only (start sender manually)"
                                                >
                                                    Run
                                                </button>
                                                {q.senderScript && (
                                                    <button
                                                        className="btn-run-query"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            runSingleQuery(q, { autoSender: true, continuousConsumption: true });
                                                        }}
                                                        disabled={!!runningQuery}
                                                        title="Run with auto-sender in live mode (no drain waiting)"
                                                    >
                                                        Run Live
                                                    </button>
                                                )}
                                            </>
                                        )}
                                    </div>
                                </div>
                                {r.duration != null && (
                                    <div className="query-card-meta">
                                        {r.duration.toFixed(1)}s | {r.kafkaMessages?.length || 0} msgs
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>

                <div className="query-results">
                    {activeQuery ? (
                        <>
                            <div className="results-header-bar">
                                <span className="results-title">{activeQuery}</span>
                                {activeResult.status === 'completed' && Object.keys(activeMetrics).length > 0 && (
                                    <span className="metrics-summary">
                                        {formatAccuracy(activeMetrics.accuracy) !== '-' && (
                                            <span>Acc: {formatAccuracy(activeMetrics.accuracy)}</span>
                                        )}
                                        {activeMetrics.avgLlmTime && (
                                            <span>LLM: {activeMetrics.avgLlmTime.toFixed(0)}ms</span>
                                        )}
                                        {activeMetrics.avgE2e && (
                                            <span>E2E: {activeMetrics.avgE2e.toFixed(0)}ms</span>
                                        )}
                                        {activeMetrics.actionRecallMicro != null && (
                                            <span>Recall: {(activeMetrics.actionRecallMicro * 100).toFixed(1)}%</span>
                                        )}
                                        {activeResult.kafkaMessages?.length > 0 && (
                                            <span>{activeResult.kafkaMessages.length} msgs</span>
                                        )}
                                    </span>
                                )}
                            </div>
                            <div className="results-tabs">
                                <button
                                    className={`results-tab ${resultsTab === 'console' ? 'active' : ''}`}
                                    onClick={() => setResultsTab('console')}
                                >
                                    Console
                                </button>
                                <button
                                    className={`results-tab ${resultsTab === 'charts' ? 'active' : ''}`}
                                    onClick={() => setResultsTab('charts')}
                                >
                                    Charts
                                </button>
                            </div>
                            {resultsTab === 'console' ? (
                                <div className="kafka-console">
                                    {consoleLines.length === 0 && (
                                        <div className="console-empty">
                                            Click "Run" to start this query...
                                        </div>
                                    )}
                                    {consoleLines.map((line, i) => (
                                        <div key={i} className={`log-line log-${line.type}`}>
                                            <span className="log-timestamp">
                                                {new Date(line.timestamp).toLocaleTimeString()}
                                            </span>
                                            <span className="log-data">{line.data}</span>
                                        </div>
                                    ))}
                                    <div ref={kafkaEndRef} />
                                </div>
                            ) : (
                                <LatencyCharts kafkaMessages={activeResult.kafkaMessages || []} chartVersion={chartVersion} />
                            )}
                        </>
                    ) : (
                        <div className="console-empty full">
                            Select a query to view results
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

// Aggregate metrics from multiple Kafka messages
function aggregateMetrics(metricsArr) {
    if (!metricsArr.length) return {};

    const accuracies = {};
    const actionRecallMicro = [];
    const actionRecallByClass = {};
    const llmTimes = [];
    const e2eTimes = [];
    const opLatencies = {};
    const betweenNodes = {};

    metricsArr.forEach(m => {
        if (m.accuracy) {
            Object.entries(m.accuracy).forEach(([key, val]) => {
                if (!accuracies[key]) accuracies[key] = [];
                if (typeof val === 'boolean') {
                    accuracies[key].push(val ? 1 : 0);
                } else if (typeof val === 'number') {
                    accuracies[key].push(val);
                }
            });
        }
        if (typeof m.action_recall_micro === 'number') {
            actionRecallMicro.push(m.action_recall_micro);
        }
        if (m.action_recall_by_class && typeof m.action_recall_by_class === 'object') {
            Object.entries(m.action_recall_by_class).forEach(([k, v]) => {
                if (typeof v !== 'number') return;
                if (!actionRecallByClass[k]) actionRecallByClass[k] = [];
                actionRecallByClass[k].push(v);
            });
        }

        if (m.llm_time_ms) llmTimes.push(m.llm_time_ms);
        if (m.avg_llm_time_ms) llmTimes.push(m.avg_llm_time_ms);

        if (m.e2e_latency_ms) e2eTimes.push(m.e2e_latency_ms);
        if (m.window_e2e_ms) e2eTimes.push(m.window_e2e_ms);

        const ops = m.operator_latencies_ms || m.avg_operator_latencies_ms || {};
        Object.entries(ops).forEach(([op, val]) => {
            if (!opLatencies[op]) opLatencies[op] = [];
            opLatencies[op].push(val);
        });

        const bns = m.between_nodes_ms || [];
        if (Array.isArray(bns)) {
            bns.forEach(b => {
                const key = `${b.from} -> ${b.to}`;
                if (!betweenNodes[key]) betweenNodes[key] = [];
                betweenNodes[key].push(b.gap_ms);
            });
        } else if (typeof bns === 'object') {
            Object.entries(bns).forEach(([key, val]) => {
                if (!betweenNodes[key]) betweenNodes[key] = [];
                betweenNodes[key].push(val);
            });
        }
    });

    const avg = arr => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null;

    return {
        accuracy: Object.fromEntries(
            Object.entries(accuracies).map(([k, v]) => [k, avg(v)])
        ),
        actionRecallMicro: avg(actionRecallMicro),
        actionRecallByClass: Object.fromEntries(
            Object.entries(actionRecallByClass).map(([k, v]) => [k, avg(v)])
        ),
        avgLlmTime: avg(llmTimes),
        avgE2e: avg(e2eTimes),
        avgOperatorLatencies: Object.fromEntries(
            Object.entries(opLatencies).map(([k, v]) => [k, avg(v)])
        ),
        avgBetweenNodes: Object.fromEntries(
            Object.entries(betweenNodes).map(([k, v]) => [k, avg(v)])
        )
    };
}

function getStatusClass(status) {
    if (!status) return 'pending';
    if (['completed', 'error', 'failed', 'pending', 'stopped'].includes(status)) return status;
    return 'running';
}

function formatAccuracy(accuracy) {
    if (!accuracy || !Object.keys(accuracy).length) return '-';
    return Object.entries(accuracy)
        .filter(([, v]) => v !== null)
        .map(([k, v]) => `${k.replace('_match', '').replace('_accuracy', '')}: ${(v * 100).toFixed(1)}%`)
        .join(', ') || '-';
}
