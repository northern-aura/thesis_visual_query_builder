import React, { useMemo, useState, useEffect } from 'react';
import { computeBoxStats, computeChartData } from '../../helpers/execution/chartStats';
import './LatencyCharts.css';

// ── Statistics ──────────────────────────────────────────────

function niceScale(min, max, targetTicks = 5) {
    if (min === max) { min = 0; max = max || 1; }
    const range = max - min;
    const rough = range / targetTicks;
    const mag = Math.pow(10, Math.floor(Math.log10(rough)));
    const residual = rough / mag;
    const nice = residual <= 1.5 ? 1 : residual <= 3 ? 2 : residual <= 7 ? 5 : 10;
    const step = nice * mag;
    const nMin = Math.floor(min / step) * step;
    const nMax = Math.ceil(max / step) * step;
    const ticks = [];
    for (let v = nMin; v <= nMax + step * 0.01; v += step) ticks.push(Math.round(v * 1e6) / 1e6);
    return { min: nMin, max: nMax, ticks };
}

// ── SVG Box Plot ────────────────────────────────────────────

function BoxPlotGroup({ datasets, width = 500, height = 260 }) {
    const margin = { top: 20, right: 20, bottom: 50, left: 65 };
    const w = width - margin.left - margin.right;
    const h = height - margin.top - margin.bottom;

    const allStats = datasets.map(d => ({ ...d, stats: computeBoxStats(d.values) })).filter(d => d.stats);
    if (!allStats.length) return <div className="chart-empty">Waiting for data...</div>;

    // Y scale from all values
    const allVals = allStats.flatMap(d => [d.stats.wLow, d.stats.wHigh, ...d.stats.outliers]);
    const vMin = allVals.reduce((m, v) => v < m ? v : m, Infinity);
    const vMax = allVals.reduce((m, v) => v > m ? v : m, -Infinity);
    const scale = niceScale(vMin, vMax);
    const yScale = v => h - ((v - scale.min) / (scale.max - scale.min)) * h;

    const boxW = Math.min(60, (w / allStats.length) * 0.6);
    const gap = w / allStats.length;

    const colors = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#ef4444', '#06b6d4'];

    return (
        <svg width={width} height={height} className="chart-svg">
            <g transform={`translate(${margin.left},${margin.top})`}>
                {/* Grid */}
                {scale.ticks.map(t => (
                    <g key={t}>
                        <line x1={0} x2={w} y1={yScale(t)} y2={yScale(t)} className="grid-line" />
                        <text x={-8} y={yScale(t) + 4} className="axis-label" textAnchor="end">
                            {t >= 1000 ? `${(t / 1000).toFixed(1)}s` : `${Math.round(t)}ms`}
                        </text>
                    </g>
                ))}
                {/* Axes */}
                <line x1={0} x2={0} y1={0} y2={h} className="axis-line" />
                <line x1={0} x2={w} y1={h} y2={h} className="axis-line" />

                {/* Box plots */}
                {allStats.map((d, i) => {
                    const cx = gap * i + gap / 2;
                    const color = colors[i % colors.length];
                    const s = d.stats;
                    return (
                        <g key={d.label}>
                            {/* Whisker low */}
                            <line x1={cx} x2={cx} y1={yScale(s.wLow)} y2={yScale(s.q1)}
                                  stroke={color} strokeWidth={1.5} strokeDasharray="4,3" />
                            <line x1={cx - boxW * 0.3} x2={cx + boxW * 0.3}
                                  y1={yScale(s.wLow)} y2={yScale(s.wLow)}
                                  stroke={color} strokeWidth={1.5} />
                            {/* Box */}
                            <rect x={cx - boxW / 2} y={yScale(s.q3)}
                                  width={boxW} height={yScale(s.q1) - yScale(s.q3)}
                                  fill={color} fillOpacity={0.2} stroke={color} strokeWidth={1.5} rx={3} />
                            {/* Median */}
                            <line x1={cx - boxW / 2} x2={cx + boxW / 2}
                                  y1={yScale(s.median)} y2={yScale(s.median)}
                                  stroke="#22c55e" strokeWidth={2.5} />
                            {/* Whisker high */}
                            <line x1={cx} x2={cx} y1={yScale(s.q3)} y2={yScale(s.wHigh)}
                                  stroke={color} strokeWidth={1.5} strokeDasharray="4,3" />
                            <line x1={cx - boxW * 0.3} x2={cx + boxW * 0.3}
                                  y1={yScale(s.wHigh)} y2={yScale(s.wHigh)}
                                  stroke={color} strokeWidth={1.5} />
                            {/* Outliers */}
                            {s.outliers.map((o, j) => (
                                <circle key={j} cx={cx} cy={yScale(o)} r={3}
                                        fill="#ef4444" fillOpacity={0.7} />
                            ))}
                            {/* Label */}
                            <text x={cx} y={h + 16} className="axis-label" textAnchor="middle">
                                {d.label}
                            </text>
                            <text x={cx} y={h + 30} className="axis-label-sub" textAnchor="middle">
                                n={s.n}
                            </text>
                        </g>
                    );
                })}
            </g>
        </svg>
    );
}

// ── SVG Scatter/Timeline ────────────────────────────────────

function ScatterPlot({ points, xLabel = 'Frame', yLabel = 'ms', width = 500, height = 220, color = '#3b82f6' }) {
    const margin = { top: 16, right: 20, bottom: 40, left: 65 };
    const w = width - margin.left - margin.right;
    const h = height - margin.top - margin.bottom;

    if (!points || points.length < 1) return <div className="chart-empty">Waiting for data...</div>;

    let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
    for (const p of points) {
        if (p.x < xMin) xMin = p.x;
        if (p.x > xMax) xMax = p.x;
        if (p.y < yMin) yMin = p.y;
        if (p.y > yMax) yMax = p.y;
    }
    const yScale = niceScale(yMin, yMax);

    const px = v => ((v - xMin) / (xMax - xMin || 1)) * w;
    const py = v => h - ((v - yScale.min) / (yScale.max - yScale.min)) * h;

    // Downsample drawn circles for long streams (SVG DOM pressure)
    const MAX_SCATTER = 500;
    const stride = points.length > MAX_SCATTER ? Math.ceil(points.length / MAX_SCATTER) : 1;
    const drawn = stride === 1 ? points : points.filter((_, i) => i % stride === 0);

    // Rolling average (window=5) — compute along drawn stride to match circle cadence
    const avgPoints = drawn.map((p, i) => {
        const centerIdx = i * stride;
        const lo = Math.max(0, centerIdx - 2);
        const hi = Math.min(points.length, centerIdx + 3);
        let sum = 0;
        for (let k = lo; k < hi; k++) sum += points[k].y;
        return { x: p.x, y: sum / (hi - lo) };
    });
    const avgPath = avgPoints.map((p, i) =>
        `${i === 0 ? 'M' : 'L'}${px(p.x)},${py(p.y)}`
    ).join(' ');

    return (
        <svg width={width} height={height} className="chart-svg">
            <g transform={`translate(${margin.left},${margin.top})`}>
                {/* Grid */}
                {yScale.ticks.map(t => (
                    <g key={t}>
                        <line x1={0} x2={w} y1={py(t)} y2={py(t)} className="grid-line" />
                        <text x={-8} y={py(t) + 4} className="axis-label" textAnchor="end">
                            {t >= 1000 ? `${(t / 1000).toFixed(1)}s` : `${Math.round(t)}`}
                        </text>
                    </g>
                ))}
                <line x1={0} x2={0} y1={0} y2={h} className="axis-line" />
                <line x1={0} x2={w} y1={h} y2={h} className="axis-line" />

                {/* Rolling average line */}
                {points.length > 2 && (
                    <path d={avgPath} fill="none" stroke={color} strokeWidth={2} />
                )}

                {/* X axis labels */}
                {drawn.filter((_, i) => i % Math.max(1, Math.floor(drawn.length / 8)) === 0).map(p => (
                    <text key={p.x} x={px(p.x)} y={h + 16} className="axis-label" textAnchor="middle">
                        {p.x}
                    </text>
                ))}
                <text x={w / 2} y={h + 32} className="axis-label" textAnchor="middle">{xLabel}</text>
            </g>
        </svg>
    );
}

// ── Stat Cards ──────────────────────────────────────────────

function StatCard({ label, value, unit, sub }) {
    return (
        <div className="stat-card">
            <div className="stat-value">{value}<span className="stat-unit">{unit}</span></div>
            <div className="stat-label">{label}</div>
            {sub && <div className="stat-sub">{sub}</div>}
        </div>
    );
}

// ── Main Component ──────────────────────────────────────────

function LatencyCharts({ kafkaMessages = [], startTime = null, chartVersion = 0 }) {
    const [elapsed, setElapsed] = useState(0);

    useEffect(() => {
        if (!startTime) { setElapsed(0); return; }
        setElapsed((Date.now() - startTime) / 1000);
        const id = setInterval(() => setElapsed((Date.now() - startTime) / 1000), 500);
        return () => clearInterval(id);
    }, [startTime]);
    // kafkaMessages array is mutated in place; chartVersion is the invalidation signal.
    const chartData = useMemo(() => computeChartData(kafkaMessages), [chartVersion]);

    if (!chartData) {
        return <div className="charts-panel"><div className="chart-empty">Run a query to see charts</div></div>;
    }

    const { llmTimes, e2eTimes, opValues, opValuesWithBp = {}, llmTimeline, e2eTimeline, accuracies, totalSkips, totalProcessed } = chartData;

    // Operator box plot datasets (sorted by median descending so LLM is first).
    // Cache computeBoxStats per operator so the sort comparator doesn't recompute O(K log K) times.
    const opDatasets = Object.entries(opValues)
        .map(([label, values]) => ({ label, values, median: computeBoxStats(values)?.median || 0 }))
        .sort((a, b) => b.median - a.median);

    // Same order for the backpressure-inclusive chart so the two read side-by-side.
    const opOrder = opDatasets.map(d => d.label);
    const opDatasetsWithBp = opOrder
        .filter(label => Array.isArray(opValuesWithBp[label]))
        .map(label => ({ label, values: opValuesWithBp[label] }));

    const llmStats = computeBoxStats(llmTimes);
    const avgAcc = Object.entries(accuracies).map(([k, vals]) => ({
        key: k.replace('_match', '').replace('_accuracy', ''),
        val: vals.reduce((a, b) => a + b, 0) / vals.length
    }));

    return (
        <div className="charts-panel">
            {/* Stat cards row */}
            <div className="stat-row">
                {startTime && (
                    <StatCard label="Elapsed" value={elapsed.toFixed(1)} unit="s" />
                )}
                {llmStats && (
                    <StatCard label="Median LLM" value={llmStats.median.toFixed(0)} unit="ms"
                              sub={`IQR: ${llmStats.q1.toFixed(0)}–${llmStats.q3.toFixed(0)}ms`} />
                )}
                {e2eTimes.length > 0 && (
                    <StatCard label="Avg E2E" value={(e2eTimes.reduce((a, b) => a + b, 0) / e2eTimes.length / 1000).toFixed(1)} unit="s" />
                )}
                <StatCard label="Processed" value={totalProcessed} unit=" frames"
                          sub={totalSkips > 0 ? `${totalSkips} skipped` : null} />
                {avgAcc.map(a => (
                    <StatCard key={a.key} label={`${a.key} acc.`} value={a.val.toFixed(1)} unit="%" />
                ))}
            </div>

            {/* Charts grid — order: E2E timeline, LLM timeline, per-op box, per-op box (no backpressure) */}
            <div className="charts-grid">
                {/* 1. E2E Latency Timeline */}
                {e2eTimeline.length >= 2 && (
                    <div className="chart-card wide">
                        <h4>End-to-End Latency Over Time</h4>
                        <ScatterPlot
                            points={e2eTimeline}
                            xLabel="Frame" yLabel="ms"
                            width={500} height={210}
                            color="#8b5cf6"
                        />
                    </div>
                )}

                {/* 2. LLM Latency Timeline */}
                {llmTimeline.length >= 2 && (
                    <div className="chart-card wide">
                        <h4>LLM Latency Over Time</h4>
                        <ScatterPlot
                            points={llmTimeline}
                            xLabel="Frame" yLabel="ms"
                            width={500} height={210}
                        />
                    </div>
                )}

                {/* 3. Per-Operator Latency (with backpressure — op time + incoming queue gap) */}
                {opDatasetsWithBp.length > 0 && (
                    <div className="chart-card wide">
                        <h4>Per-Operator Latency (with backpressure)</h4>
                        <BoxPlotGroup
                            datasets={opDatasetsWithBp}
                            width={Math.max(350, opDatasetsWithBp.length * 100 + 100)} height={240}
                        />
                    </div>
                )}

                {/* 4. Per-Operator Latency (pure processing, no backpressure) */}
                {opDatasets.length > 0 && (
                    <div className="chart-card wide">
                        <h4>Per-Operator Latency (without backpressure)</h4>
                        <BoxPlotGroup
                            datasets={opDatasets}
                            width={Math.max(350, opDatasets.length * 100 + 100)} height={240}
                        />
                    </div>
                )}
            </div>
        </div>
    );
}

export default React.memo(LatencyCharts);
