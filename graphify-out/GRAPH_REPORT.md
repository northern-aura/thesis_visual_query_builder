# Graph Report - .  (2026-04-22)

## Corpus Check
- Large: 438 files, 680838 words

## Summary
- 272 nodes · 385 edges · 19 communities detected
- Extraction: 77% EXTRACTED · 23% INFERRED · 0% AMBIGUOUS · INFERRED: 89 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Backend API & Script Executor|Backend API & Script Executor]]
- [[_COMMUNITY_Direct Python Export Generator|Direct Python Export Generator]]
- [[_COMMUNITY_ReactFlow Node Components|ReactFlow Node Components]]
- [[_COMMUNITY_Docker Manager|Docker Manager]]
- [[_COMMUNITY_Metrics CSV Renderer|Metrics CSV Renderer]]
- [[_COMMUNITY_Metrics Dashboard (Frontend)|Metrics Dashboard (Frontend)]]
- [[_COMMUNITY_PDF Overview Generator|PDF Overview Generator]]
- [[_COMMUNITY_PyFlink Map Operators (Runtime)|PyFlink Map Operators (Runtime)]]
- [[_COMMUNITY_LLM Client (GPTOllamavLLM)|LLM Client (GPT/Ollama/vLLM)]]
- [[_COMMUNITY_Latency Charts (Frontend)|Latency Charts (Frontend)]]
- [[_COMMUNITY_Thesis Plots Renderer|Thesis Plots Renderer]]
- [[_COMMUNITY_SSE Client (Execution)|SSE Client (Execution)]]
- [[_COMMUNITY_SSE Client (Kafka)|SSE Client (Kafka)]]
- [[_COMMUNITY_Backend FastAPI Entry|Backend FastAPI Entry]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]

## God Nodes (most connected - your core abstractions)
1. `DockerManager` - 18 edges
2. `ScriptStorage` - 18 edges
3. `ScriptExecutor` - 16 edges
4. `ExecuteResponse` - 13 edges
5. `DockerStatusResponse` - 13 edges
6. `ExecutionInfo` - 13 edges
7. `ExecutionsListResponse` - 13 edges
8. `ExecuteRequest` - 12 edges
9. `API routes for script execution and management.` - 9 edges
10. `Start script execution.      Returns execution_id and stream URL for SSE connect` - 9 edges

## Surprising Connections (you probably didn't know these)
- `generateDirectPython()` --calls--> `generateImports()`  [INFERRED]
  /mnt/c/Users/funky/Downloads/reactflow-query-builder-master(1)/reactflow-query-builder-master/src/helpers/export/directPythonExport.js → /mnt/c/Users/funky/Downloads/reactflow-query-builder-master(1)/reactflow-query-builder-master/src/helpers/export/Methodtemplates.js
- `generateDirectPython()` --calls--> `generateMapComputeMetricsClass()`  [INFERRED]
  /mnt/c/Users/funky/Downloads/reactflow-query-builder-master(1)/reactflow-query-builder-master/src/helpers/export/directPythonExport.js → /mnt/c/Users/funky/Downloads/reactflow-query-builder-master(1)/reactflow-query-builder-master/src/helpers/export/Methodtemplates.js
- `generateMainPipeline()` --calls--> `getNodeParameters()`  [INFERRED]
  /mnt/c/Users/funky/Downloads/reactflow-query-builder-master(1)/reactflow-query-builder-master/src/helpers/export/directPythonExport.js → /mnt/c/Users/funky/Downloads/reactflow-query-builder-master(1)/reactflow-query-builder-master/src/helpers/export/utils/export-utils.js
- `API routes for script execution and management.` --uses--> `DockerManager`  [INFERRED]
  /mnt/c/Users/funky/Downloads/reactflow-query-builder-master(1)/reactflow-query-builder-master/backend/api/routes.py → /mnt/c/Users/funky/Downloads/reactflow-query-builder-master(1)/reactflow-query-builder-master/backend/services/docker_manager.py
- `Start script execution.      Returns execution_id and stream URL for SSE connect` --uses--> `DockerManager`  [INFERRED]
  /mnt/c/Users/funky/Downloads/reactflow-query-builder-master(1)/reactflow-query-builder-master/backend/api/routes.py → /mnt/c/Users/funky/Downloads/reactflow-query-builder-master(1)/reactflow-query-builder-master/backend/services/docker_manager.py

## Communities

### Community 0 - "Backend API & Script Executor"
Cohesion: 0.08
Nodes (45): BaseModel, execute_script(), get_docker_status(), get_execution_details(), get_execution_logs(), list_executions(), API routes for script execution and management., Get Docker containers status. (+37 more)

### Community 1 - "Direct Python Export Generator"
Cohesion: 0.1
Nodes (5): generateDirectPython(), generateMainPipeline(), getOrderedNodes(), generateImports(), generateMapComputeMetricsClass()

### Community 2 - "ReactFlow Node Components"
Cohesion: 0.11
Nodes (6): getNodeParameters(), generateStructuredJSON(), BlockEndNode(), BlockStartNode(), CircleNode(), getNodeIcon()

### Community 3 - "Docker Manager"
Cohesion: 0.15
Nodes (10): DockerManager, Docker container management service., Build pyflink Docker image if it doesn't exist., Wait for all containers to be running and healthy.          Args:             ma, Manages Docker containers for script execution., Initialize Docker client., Check status of required containers.          Returns:             Dict with doc, Get container uptime as human-readable string. (+2 more)

### Community 5 - "Metrics CSV Renderer"
Cohesion: 0.29
Nodes (13): embed_image(), fmt_num(), fmt_pct(), load_best_runs(), main(), _parse_row(), Map a raw CSV row to a dict, choosing the schema based on field count.      summ, Return {query_title: best_row_dict} where best = max(message_count), tie-break l (+5 more)

### Community 6 - "Metrics Dashboard (Frontend)"
Cohesion: 0.19
Nodes (5): buildNodesAndEdges(), extractQueryMeta(), formatAccuracy(), MetricsDashboard(), sortByNext()

### Community 7 - "PDF Overview Generator"
Cohesion: 0.26
Nodes (9): FPDF, draw_table(), main(), _measure_row_height(), OverviewPDF, Generate a supervisor-friendly PDF overview of all query presets.  Reads nothing, _render_header(), _render_row() (+1 more)

### Community 8 - "PyFlink Map Operators (Runtime)"
Cohesion: 0.23
Nodes (6): MapFunction, MapAddMetrics, MapDecodeStream, MapPromptLLM, MapRecolorImage, MapResizeImage

### Community 9 - "LLM Client (GPT/Ollama/vLLM)"
Cohesion: 0.27
Nodes (10): prompt_llm(), Send multiple images to GPT-4o in a single API call., Send multiple images to an Ollama model in a single API call., Send multiple images to a vLLM model in a single API call., send_to_gpt(), send_to_gpt_multi(), send_to_ollama(), send_to_ollama_multi() (+2 more)

### Community 10 - "Latency Charts (Frontend)"
Cohesion: 0.29
Nodes (7): buildChartSummary(), computeBoxStats(), computeChartData(), BoxPlotGroup(), LatencyCharts(), niceScale(), ScatterPlot()

### Community 11 - "Thesis Plots Renderer"
Cohesion: 0.46
Nodes (7): _accuracy_bar(), _llm_box(), load_metrics(), main(), _operator_boxes(), render_query(), _timeline()

### Community 12 - "SSE Client (Execution)"
Cohesion: 0.4
Nodes (1): ExecutionSSEClient

### Community 13 - "SSE Client (Kafka)"
Cohesion: 0.5
Nodes (1): KafkaSSEClient

### Community 14 - "Backend FastAPI Entry"
Cohesion: 0.4
Nodes (3): health_check(), FastAPI application for ReactFlow Query Builder backend., Health check endpoint.

### Community 15 - "Community 15"
Cohesion: 0.5
Nodes (2): Get or create Docker client lazily., Execute script inside pyflink Docker container.          Args:             execu

### Community 16 - "Community 16"
Cohesion: 0.67
Nodes (1): ExportButton()

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Configuration settings for the backend.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): FilterFunction

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): ReduceFunction

## Knowledge Gaps
- **40 isolated node(s):** `Configuration settings for the backend.`, `FastAPI application for ReactFlow Query Builder backend.`, `Health check endpoint.`, `Pydantic models for request/response schemas.`, `Request model for script execution.` (+35 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `SSE Client (Execution)`** (6 nodes): `sseClient.js`, `ExecutionSSEClient`, `.close()`, `.connect()`, `.constructor()`, `.getConnectionState()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `SSE Client (Kafka)`** (5 nodes): `KafkaSSEClient`, `.close()`, `.connect()`, `.constructor()`, `kafkaSseClient.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (4 nodes): `Get or create Docker client lazily.`, `Execute script inside pyflink Docker container.          Args:             execu`, `.execute_in_docker()`, `._get_client()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (3 nodes): `ExportButton()`, `exportButton.jsx`, `ExportButton.jsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (2 nodes): `config.py`, `Configuration settings for the backend.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `FilterFunction`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `ReduceFunction`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DockerManager` connect `Docker Manager` to `Backend API & Script Executor`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Why does `ScriptExecutor` connect `Backend API & Script Executor` to `Community 15`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `DockerManager` (e.g. with `API routes for script execution and management.` and `Start script execution.      Returns execution_id and stream URL for SSE connect`) actually correct?**
  _`DockerManager` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `ScriptStorage` (e.g. with `API routes for script execution and management.` and `Start script execution.      Returns execution_id and stream URL for SSE connect`) actually correct?**
  _`ScriptStorage` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `ScriptExecutor` (e.g. with `API routes for script execution and management.` and `Start script execution.      Returns execution_id and stream URL for SSE connect`) actually correct?**
  _`ScriptExecutor` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `ExecuteResponse` (e.g. with `API routes for script execution and management.` and `Start script execution.      Returns execution_id and stream URL for SSE connect`) actually correct?**
  _`ExecuteResponse` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `DockerStatusResponse` (e.g. with `API routes for script execution and management.` and `Start script execution.      Returns execution_id and stream URL for SSE connect`) actually correct?**
  _`DockerStatusResponse` has 10 INFERRED edges - model-reasoned connections that need verification._