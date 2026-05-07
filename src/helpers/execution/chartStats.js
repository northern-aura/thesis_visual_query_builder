// Shared statistics + chart-data derivation used by LatencyCharts and MetricsDashboard's save step.

export function computeBoxStats(values) {
    if (!values || values.length < 2) return null;
    const sorted = [...values].filter(v => v != null && isFinite(v)).sort((a, b) => a - b);
    const n = sorted.length;
    if (n < 2) return null;
    const q1 = sorted[Math.floor(n * 0.25)];
    const median = sorted[Math.floor(n * 0.5)];
    const q3 = sorted[Math.floor(n * 0.75)];
    const iqr = q3 - q1;
    const wLow = Math.max(sorted[0], q1 - 1.5 * iqr);
    const wHigh = Math.min(sorted[n - 1], q3 + 1.5 * iqr);
    const outliers = sorted.filter(v => v < wLow || v > wHigh);
    const mean = sorted.reduce((a, b) => a + b, 0) / n;
    return { min: sorted[0], q1, median, q3, max: sorted[n - 1], wLow, wHigh, outliers, mean, n };
}

function toNonNegativeInt(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return null;
    return Math.max(0, Math.round(n));
}

function normalizeResultLabel(value) {
    if (value == null) return '';
    return String(value).trim().toUpperCase();
}

function extractWindowResultCounts(result) {
    let processed = 0;
    let skips = 0;
    let seen = false;

    const addCount = (labelRaw, countRaw = 1) => {
        const count = toNonNegativeInt(countRaw);
        if (count == null || count === 0) return;
        seen = true;
        const label = normalizeResultLabel(labelRaw);
        if (label === 'SKIP' || label === 'SKIPPED') skips += count;
        else processed += count;
    };

    if (Array.isArray(result)) {
        result.forEach((item) => {
            if (Array.isArray(item) && item.length >= 2) {
                addCount(item[0], item[1]);
                return;
            }
            if (item && typeof item === 'object') {
                if ('value' in item && 'count' in item) {
                    addCount(item.value, item.count);
                    return;
                }
                if ('result' in item && 'count' in item) {
                    addCount(item.result, item.count);
                    return;
                }
            }
            addCount(item, 1);
        });
    } else if (result != null && result !== '') {
        addCount(result, 1);
    }

    if (!seen) return null;
    return { processed, skips, total: processed + skips };
}

// Derives the chart-ready data from an array of Kafka messages.
// Output shape matches what LatencyCharts renders, so plots can be reproduced offline.
export function computeChartData(kafkaMessages) {
    if (!kafkaMessages || !kafkaMessages.length) return null;

    const isWindowed = kafkaMessages[0]?.frames != null;

    const llmTimes = [];
    const e2eTimes = [];
    const opValues = {};        // pure processing time per op (no queueing)
    const opValuesWithBp = {};  // op time + incoming between-nodes gap (backpressure included)
    const llmTimeline = [];
    const e2eTimeline = [];
    let totalSkips = 0;
    let totalProcessed = 0;

    kafkaMessages.forEach((msg, idx) => {
        const m = msg.metrics || {};

        if (isWindowed) {
            if (Array.isArray(msg.llm_time)) {
                msg.llm_time.forEach(t => {
                    const ms = t * 1000;
                    llmTimes.push(ms);
                    llmTimeline.push({ x: llmTimeline.length + 1, y: ms });
                });
            }
            if (m.window_e2e_ms) {
                e2eTimes.push(m.window_e2e_ms);
                e2eTimeline.push({ x: idx + 1, y: m.window_e2e_ms });
            }
            const ops = m.avg_operator_latencies_ms || {};
            Object.entries(ops).forEach(([op, val]) => {
                if (!opValues[op]) opValues[op] = [];
                opValues[op].push(val);
            });
            // No between-nodes data in windowed mode — backpressure variant mirrors pure values.
            Object.entries(ops).forEach(([op, val]) => {
                if (!opValuesWithBp[op]) opValuesWithBp[op] = [];
                opValuesWithBp[op].push(val);
            });
            const resultCounts = extractWindowResultCounts(msg.result);
            const frameCount = toNonNegativeInt(msg.frames) || 0;
            const llmProcessed = Array.isArray(msg.llm_time)
                ? msg.llm_time.filter(t => Number.isFinite(Number(t)) && Number(t) > 0).length
                : 0;

            let messageProcessed = 0;
            let messageSkips = 0;
            if (frameCount > 0) {
                // Prefer explicit frame count from pipeline payload when available.
                messageProcessed = frameCount;
                if (resultCounts) {
                    messageSkips = Math.max(resultCounts.skips, frameCount - resultCounts.processed);
                } else if (llmProcessed > 0) {
                    messageSkips = Math.max(0, frameCount - llmProcessed);
                }
            } else if (llmProcessed > 0) {
                // Fallback for filtered/distinct window outputs where `result` can be [].
                messageProcessed = llmProcessed;
                messageSkips = resultCounts?.skips || 0;
            } else if (resultCounts) {
                messageProcessed = resultCounts.processed;
                messageSkips = resultCounts.skips;
            } else {
                // Last-resort fallback: one emitted window message implies one processed item.
                messageProcessed = 1;
            }
            totalProcessed += messageProcessed;
            totalSkips += messageSkips;
        } else {
            const llmMs = m.llm_time_ms || (msg.llm_time ? msg.llm_time * 1000 : 0);
            if (llmMs > 0) {
                llmTimes.push(llmMs);
                llmTimeline.push({ x: idx + 1, y: llmMs });
                totalProcessed++;
            } else {
                totalSkips++;
            }
            if (m.e2e_latency_ms) {
                e2eTimes.push(m.e2e_latency_ms);
                e2eTimeline.push({ x: idx + 1, y: m.e2e_latency_ms });
            }
            const ops = m.operator_latencies_ms || {};
            Object.entries(ops).forEach(([op, val]) => {
                if (!opValues[op]) opValues[op] = [];
                opValues[op].push(val);
            });
            // Backpressure-inclusive breakdown.
            // Per-message budget:  e2e = sum(op) + sum(between_nodes_ms) + kafka_wait
            // The dominant backpressure term is `kafka_wait`: how long the frame sat in the
            // Kafka topic before the source read it. Attribute that to the first operator in
            // the chain (the one with no incoming gap), so its box reflects end-to-end queueing.
            const gaps = Array.isArray(m.between_nodes_ms) ? m.between_nodes_ms : [];
            const incomingGap = {};
            const opsWithIncoming = new Set();
            gaps.forEach(g => {
                if (g && g.to != null) {
                    incomingGap[g.to] = (incomingGap[g.to] || 0) + (g.gap_ms || 0);
                    opsWithIncoming.add(g.to);
                }
            });
            const opEntries = Object.entries(ops);
            const firstOp = opEntries.find(([op]) => !opsWithIncoming.has(op))?.[0]
                         ?? opEntries[0]?.[0];
            const opSum = opEntries.reduce((s, [, v]) => s + (v || 0), 0);
            const gapSum = gaps.reduce((s, g) => s + (g?.gap_ms || 0), 0);
            const kafkaWait = Math.max(0, (m.e2e_latency_ms || 0) - opSum - gapSum);
            opEntries.forEach(([op, val]) => {
                if (!opValuesWithBp[op]) opValuesWithBp[op] = [];
                const queueing = (incomingGap[op] || 0) + (op === firstOp ? kafkaWait : 0);
                opValuesWithBp[op].push(val + queueing);
            });
        }
    });

    const accuracies = {};
    kafkaMessages.forEach(msg => {
        const acc = msg.metrics?.accuracy || {};
        Object.entries(acc).forEach(([k, v]) => {
            if (!accuracies[k]) accuracies[k] = [];
            if (typeof v === 'boolean') accuracies[k].push(v ? 100 : 0);
            else if (typeof v === 'number') accuracies[k].push(v * 100);
        });
    });

    return { llmTimes, e2eTimes, opValues, opValuesWithBp, llmTimeline, e2eTimeline, accuracies, totalSkips, totalProcessed, isWindowed };
}

// Builds a serializable summary — this is what gets saved to metrics/<slug>.json.
export function buildChartSummary(kafkaMessages) {
    const chart = computeChartData(kafkaMessages);
    if (!chart) return null;

    const boxStats = {
        llm: computeBoxStats(chart.llmTimes),
        e2e: computeBoxStats(chart.e2eTimes),
        operators: Object.fromEntries(
            Object.entries(chart.opValues).map(([op, vals]) => [op, computeBoxStats(vals)])
        ),
        operators_with_backpressure: Object.fromEntries(
            Object.entries(chart.opValuesWithBp || {}).map(([op, vals]) => [op, computeBoxStats(vals)])
        )
    };

    const accuracyMeans = Object.fromEntries(
        Object.entries(chart.accuracies).map(([k, vals]) => [
            k,
            vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null
        ])
    );

    return {
        is_windowed: chart.isWindowed,
        total_processed: chart.totalProcessed,
        total_skips: chart.totalSkips,
        box_stats: boxStats,
        accuracy_means_pct: accuracyMeans,
        timelines: {
            llm: chart.llmTimeline,
            e2e: chart.e2eTimeline
        },
        raw: {
            llm_times_ms: chart.llmTimes,
            e2e_times_ms: chart.e2eTimes,
            operator_latencies_ms: chart.opValues,
            operator_latencies_with_bp_ms: chart.opValuesWithBp,
            accuracies_pct: chart.accuracies
        }
    };
}
