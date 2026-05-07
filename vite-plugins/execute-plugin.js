/**
 * Vite plugin for executing Python scripts directly.
 * No separate backend needed - everything runs in the Vite dev server!
 */
import { spawn, spawnSync } from 'child_process';
import { writeFileSync, existsSync, mkdirSync, appendFileSync, readFileSync, copyFileSync, readdirSync } from 'fs';
import { join } from 'path';

// Load environment variables from .env file
const envPath = join(process.cwd(), '.env');
if (existsSync(envPath)) {
  const envContent = readFileSync(envPath, 'utf-8');
  envContent.split('\n').forEach(line => {
    const trimmedLine = line.trim();
    if (trimmedLine && !trimmedLine.startsWith('#')) {
      const [key, ...valueParts] = trimmedLine.split('=');
      if (key && valueParts.length > 0) {
        const value = valueParts.join('=').trim();
        process.env[key.trim()] = value;
      }
    }
  });
  console.log('✅ Loaded environment variables from .env file');
}

// Storage for active executions
const activeExecutions = new Map();
const executionHistory = [];

export function executePlugin() {
  // Ensure directories exist
  const scriptsDir = join(process.cwd(), 'scripts');
  const resultsDir = join(process.cwd(), 'results');
  const helperModulesDir = join(process.cwd(), 'running', 'Scripts');

  const metricsDir = join(resultsDir, 'metrics');
  const plotsDir = join(resultsDir, 'plots');
  const logsDir = join(resultsDir, 'logs');

  if (!existsSync(scriptsDir)) mkdirSync(scriptsDir, { recursive: true });
  if (!existsSync(resultsDir)) mkdirSync(resultsDir, { recursive: true });
  if (!existsSync(metricsDir)) mkdirSync(metricsDir, { recursive: true });
  if (!existsSync(plotsDir)) mkdirSync(plotsDir, { recursive: true });
  if (!existsSync(logsDir)) mkdirSync(logsDir, { recursive: true });

  // Prefer the project's Python venv if present; fall back to system `python`.
  const VENV_BASE = join(process.cwd(), 'running', 'Topics', 'Cars', 'Data', 'venv');
  const VENV_PY_WIN = join(VENV_BASE, 'Scripts', 'python.exe');
  const VENV_PY_POSIX = join(VENV_BASE, 'bin', 'python');
  const PYTHON_EXE = existsSync(VENV_PY_WIN) ? VENV_PY_WIN
                   : existsSync(VENV_PY_POSIX) ? VENV_PY_POSIX
                   : 'python';
  console.log(`[python] Using interpreter: ${PYTHON_EXE}`);

  // Auto-copy helper modules from running/Scripts/ to scripts/
  if (existsSync(helperModulesDir)) {
    try {
      const helperFiles = readdirSync(helperModulesDir).filter(f => f.endsWith('.py'));
      helperFiles.forEach(file => {
        const srcPath = join(helperModulesDir, file);
        const destPath = join(scriptsDir, file);
        copyFileSync(srcPath, destPath);
      });
      if (helperFiles.length > 0) {
        console.log(`📦 Copied ${helperFiles.length} helper module(s): ${helperFiles.join(', ')}`);
      }
    } catch (error) {
      console.warn('⚠️  Warning: Could not copy helper modules:', error.message);
    }
  }

  return {
    name: 'execute-plugin',

    configureServer(server) {
      console.log('✅ Execute plugin loaded - Python scripts can run directly from frontend!\n');

      // ==========================================
      // POST /api/execute - Start script execution
      // ==========================================
      server.middlewares.use('/api/execute', async (req, res, next) => {
        if (req.method !== 'POST') return next();

        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', () => {
          try {
            const { script_name, script_content, project_name, local, cwd } = JSON.parse(body);

            // Generate unique execution ID
            const timestamp = Date.now();
            const hash = Math.abs(hashCode(script_name)) % 10000;
            const execution_id = `exec_${timestamp}_${hash.toString().padStart(4, '0')}`;

            // For Docker scripts, replace localhost Kafka address with Docker internal address
            // Local scripts keep localhost:9092 since they talk to Kafka from the host
            let processedScript = script_content;
            if (!local) {
              processedScript = script_content
                .replace(/localhost:9092/g, 'kafka:9093')      // Kafka internal address
                .replace(/127\.0\.0\.1:9092/g, 'kafka:9093');  // Also handle 127.0.0.1
            }

            // Best-effort: extract Kafka sink info from script so the UI can subscribe
            // to results (Kafka topics) while the job runs.
            const kafkaOutputTopic = extractKafkaTopicFromScript(processedScript);
            const kafkaBootstrapServers = extractKafkaBootstrapFromScript(processedScript);

            // Kill stale streaming jobs before topic cleanup so they cannot write
            // old results into freshly recreated topics.
            if (!local) {
              const cancelled = cancelRunningFlinkJobs();
              if (cancelled.length > 0) {
                console.log(`[Execute] Cancelled ${cancelled.length} stale Flink job(s) before topic cleanup: ${cancelled.join(', ')}`);
              }
            }

            // Clear the output topic so the UI only sees results from this execution.
            // Delete + auto-recreate ensures fromBeginning consumers get a clean slate.
            if (kafkaOutputTopic && !local) {
              const kafkaContainer = resolveDockerContainerName('kafka');
              if (kafkaContainer) {
                try {
                  spawnSync('docker', [
                    'exec', kafkaContainer,
                    'kafka-topics.sh', '--delete',
                    '--topic', kafkaOutputTopic,
                    '--bootstrap-server', 'localhost:9092'
                  ], { encoding: 'utf8', timeout: 10000 });
                  console.log(`[Execute] 🗑️  Cleared output topic: ${kafkaOutputTopic}`);
                  // Recreate immediately so consumers don't hit LEADER_NOT_AVAILABLE
                  spawnSync('docker', [
                    'exec', kafkaContainer,
                    'kafka-topics.sh', '--create',
                    '--topic', kafkaOutputTopic,
                    '--bootstrap-server', 'localhost:9092',
                    '--partitions', '1',
                    '--replication-factor', '1',
                    '--if-not-exists'
                  ], { encoding: 'utf8', timeout: 10000 });
                } catch {
                  // Topic might not exist yet — that's fine
                }
              }
            }

            // Prevent frame leakage from an old streaming job into the next queued run.
            if (!local) {
              const cancelled = cancelRunningFlinkJobs();
              if (cancelled.length > 0) {
                console.log(`[Execute] Cancelled ${cancelled.length} stale Flink job(s) before starting ${execution_id}: ${cancelled.join(', ')}`);
              }
            }

            // Save script to file
            const scriptPath = join(scriptsDir, `${execution_id}.py`);
            writeFileSync(scriptPath, processedScript);

            // Save metadata
            const metadata = {
              execution_id,
              script_name,
              project_name,
              local: !!local,
              cwd: cwd || null,
              status: 'queued',
              started_at: new Date().toISOString(),
              script_path: scriptPath
            };

            activeExecutions.set(execution_id, metadata);
            executionHistory.unshift(metadata);

            console.log(`[Execute] 📝 Script saved: ${execution_id}`);

            // Return execution info
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({
              execution_id,
              status: 'queued',
              stream_url: `/api/execute/${execution_id}/stream`,
              kafka: {
                output_topic: kafkaOutputTopic,
                bootstrap_servers: kafkaBootstrapServers
              }
            }));
          } catch (error) {
            console.error('[Execute] Error:', error);
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: error.message }));
          }
        });
      });

      // ==========================================
      // GET /api/execute/:id/stream - Stream execution via SSE
      // ==========================================
      server.middlewares.use('/api/execute', (req, res, next) => {
        if (req.method !== 'GET') return next();

        const match = req.url.match(/^\/([^/]+)\/stream$/);
        if (!match) return next();

        const execution_id = match[1];
        const metadata = activeExecutions.get(execution_id);

        if (!metadata) {
          res.writeHead(404, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Execution not found' }));
          return;
        }

        // Set up SSE headers
        res.writeHead(200, {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
          'X-Accel-Buffering': 'no'
        });

        // Send start event
        sendSSE(res, { type: 'started', execution_id, timestamp: new Date().toISOString() });
        sendSSE(res, { type: 'info', data: metadata.local ? 'Running script locally...' : 'Submitting job to Flink cluster...', timestamp: new Date().toISOString() });

        console.log(`[Execute] ▶️  Starting: ${execution_id}${metadata.local ? ' (local)' : ''}`);

        // Update status
        metadata.status = 'running';

        // Prepare log file
        const logPath = join(logsDir, `${execution_id}.log`);
        const resultPath = join(logsDir, `${execution_id}_results.txt`);

        const startTime = Date.now();
        let python;

        if (metadata.local) {
          // Local execution — spawn python directly in the host venv
          const localCwd = metadata.cwd
            ? join(process.cwd(), metadata.cwd)
            : process.cwd();
          python = spawn(PYTHON_EXE, [metadata.script_path], {
            cwd: localCwd,
            stdio: ['ignore', 'pipe', 'pipe']
          });
        } else {
          // Docker execution — submit PyFlink job to Flink cluster

          // Collect ONLY real helper modules (not old exec scripts) to distribute with the job
          const helperFiles = [];
          const scriptsPath = '/scripts';
          try {
            const files = readdirSync(scriptsDir);
            files.forEach(file => {
              // Skip execution scripts (exec_*) and only include actual helper modules
              if (file.endsWith('.py') && !file.startsWith('exec_')) {
                helperFiles.push(`${scriptsPath}/${file}`);
              }
            });
            if (helperFiles.length > 0) {
              console.log(`📎 Distributing ${helperFiles.length} helper module(s) with job: ${helperFiles.map(f => f.split('/').pop()).join(', ')}`);
            }
          } catch (err) {
            console.warn('⚠️  Warning: Could not read helper files:', err.message);
          }

          // Build docker command arguments
          const apiKey = process.env.OPENAI_API_KEY;
          if (apiKey) {
            console.log('✅ OPENAI_API_KEY found in environment (length:', apiKey.length, ')');
            const apiKeyPath = join(scriptsDir, '.openai_api_key');
            writeFileSync(apiKeyPath, apiKey);
          } else {
            console.warn('⚠️  WARNING: OPENAI_API_KEY not found in environment variables');
          }

          const dockerArgs = [
            'exec',
            '-e', 'PYTHONPATH=/scripts',
            'jobmanager',
            'flink',
            'run',
            '-py',
            `/scripts/${execution_id}.py`
          ];

          if (helperFiles.length > 0) {
            dockerArgs.push('--pyFiles', helperFiles.join(','));
          }

          python = spawn('docker', dockerArgs, {
            cwd: process.cwd(),
            stdio: ['ignore', 'pipe', 'pipe']
          });
        }

        // Store process for potential cancellation
        metadata.process = python;

        // Handle stdout
        python.stdout.on('data', (data) => {
          const output = data.toString();

          // Capture Flink JobID so we can cancel the job when stopping
          if (!metadata.local) {
            const jobIdMatch = output.match(/Job has been submitted with JobID\s+([a-f0-9]+)/);
            if (jobIdMatch) {
              metadata.flinkJobId = jobIdMatch[1];
              console.log(`[Execute] 🔗 Captured Flink JobID: ${metadata.flinkJobId}`);
            }
          }

          // Append to log file
          appendFileSync(logPath, output);
          appendFileSync(resultPath, output);

          // Send to frontend
          sendSSE(res, {
            type: 'stdout',
            data: output,
            timestamp: new Date().toISOString()
          });

          // Console log
          console.log(`[Execute] [${execution_id}] ${output.trim()}`);
        });

        // Handle stderr
        python.stderr.on('data', (data) => {
          const output = data.toString();

          // Append to log file
          appendFileSync(logPath, `[ERROR] ${output}`);

          // Send to frontend
          sendSSE(res, {
            type: 'stderr',
            data: output,
            timestamp: new Date().toISOString()
          });

          // Console log
          console.error(`[Execute] [${execution_id}] ERROR: ${output.trim()}`);
        });

        // Handle completion
        python.on('close', (code) => {
          const duration = ((Date.now() - startTime) / 1000).toFixed(2);

          metadata.status = code === 0 ? 'completed' : 'failed';
          metadata.exit_code = code;
          metadata.completed_at = new Date().toISOString();
          metadata.duration_seconds = parseFloat(duration);

          console.log(`[Execute] ${code === 0 ? '✅' : '❌'} Finished: ${execution_id} (exit code: ${code}, duration: ${duration}s)`);

          // Send completion event
          sendSSE(res, {
            type: 'completed',
            exit_code: code,
            duration_seconds: parseFloat(duration),
            timestamp: new Date().toISOString()
          });

          // Close SSE connection
          res.end();

          // Cleanup process reference
          delete metadata.process;
        });

        // Handle errors
        python.on('error', (error) => {
          console.error(`[Execute] ❌ Error executing ${execution_id}:`, error.message);

          metadata.status = 'error';

          sendSSE(res, {
            type: 'error',
            data: `Failed to execute Python: ${error.message}`,
            timestamp: new Date().toISOString()
          });

          res.end();
        });

        // Handle client disconnect
        req.on('close', () => {
          console.log(`[Execute] Client disconnected from ${execution_id}`);
        });
      });

      // ==========================================
      // GET /api/executions - List execution history
      // ==========================================
      server.middlewares.use('/api/executions', (req, res, next) => {
        if (req.method !== 'GET') return next();
        if (!req.url.startsWith('/api/executions')) return next();

        const limit = 50;
        const executions = executionHistory.slice(0, limit).map(e => ({
          execution_id: e.execution_id,
          script_name: e.script_name,
          project_name: e.project_name,
          status: e.status,
          exit_code: e.exit_code,
          started_at: e.started_at,
          completed_at: e.completed_at,
          duration_seconds: e.duration_seconds
        }));

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ executions, total: executions.length }));
      });

      // ==========================================
      // GET /api/executions/:id/logs - Get execution logs
      // ==========================================
      server.middlewares.use('/api/executions', (req, res, next) => {
        if (req.method !== 'GET') return next();

        const match = req.url.match(/^\/api\/executions\/([^/]+)\/logs$/);
        if (!match) return next();

        const execution_id = match[1];
        const logPath = join(logsDir, `${execution_id}.log`);

        if (!existsSync(logPath)) {
          res.writeHead(404, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Logs not found' }));
          return;
        }

        const logs = readFileSync(logPath, 'utf-8');
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ execution_id, logs }));
      });

      // ==========================================
      // DELETE /api/executions/:id - Stop execution
      // ==========================================
      server.middlewares.use('/api/executions', (req, res, next) => {
        if (req.method !== 'DELETE') return next();

        const match = req.url.match(/^\/api\/executions\/([^/]+)$/);
        if (!match) return next();

        const execution_id = match[1];
        const metadata = activeExecutions.get(execution_id);

        if (!metadata || !metadata.process) {
          res.writeHead(404, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Execution not found or not running' }));
          return;
        }

        // Kill the client process (docker exec or local python)
        metadata.process.kill('SIGTERM');
        metadata.status = 'stopped';
        console.log(`[Execute] 🛑 Stopped: ${execution_id}`);

        // For Flink jobs, also cancel the job in the cluster so it frees task slots
        if (metadata.flinkJobId && !metadata.local) {
          try {
            const cancel = spawnSync('docker', [
              'exec', 'jobmanager', 'flink', 'cancel', metadata.flinkJobId
            ], { encoding: 'utf8', timeout: 10000 });
            if (cancel.status === 0) {
              console.log(`[Execute] 🗑️  Cancelled Flink job: ${metadata.flinkJobId}`);
            } else {
              console.warn(`[Execute] ⚠️  Could not cancel Flink job ${metadata.flinkJobId}: ${(cancel.stderr || '').trim()}`);
            }
          } catch (err) {
            console.warn(`[Execute] ⚠️  Error cancelling Flink job: ${err.message}`);
          }
        }

        if (!metadata.local) {
          const cancelled = cancelRunningFlinkJobs();
          if (cancelled.length > 0) {
            console.log(`[Execute] Cancelled remaining Flink job(s): ${cancelled.join(', ')}`);
          }
        }

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ execution_id, status: 'stopped' }));
      });

      // ==========================================
      // POST /api/kafka/clear-topic - Delete and recreate a Kafka topic
      // ==========================================
      server.middlewares.use('/api/kafka/clear-topic', (req, res, next) => {
        if (req.method !== 'POST') return next();

        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', () => {
          try {
            const { topic } = JSON.parse(body);
            if (!topic) {
              res.writeHead(400, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: 'Missing required field: topic' }));
              return;
            }

            const kafkaContainer = resolveDockerContainerName('kafka');
            if (!kafkaContainer) {
              res.writeHead(500, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: 'Kafka container not found' }));
              return;
            }

            // Delete topic (async on broker — returns before deletion is final)
            spawnSync('docker', [
              'exec', kafkaContainer,
              'kafka-topics.sh', '--delete',
              '--topic', topic,
              '--bootstrap-server', 'localhost:9092'
            ], { encoding: 'utf8', timeout: 10000 });

            // Poll until the delete is fully propagated — --describe returns non-zero when gone.
            const deadline = Date.now() + 10000;
            while (Date.now() < deadline) {
              const describe = spawnSync('docker', [
                'exec', kafkaContainer,
                'kafka-topics.sh', '--describe',
                '--topic', topic,
                '--bootstrap-server', 'localhost:9092'
              ], { encoding: 'utf8', timeout: 5000 });
              if (describe.status !== 0) break;
              // Busy-wait ~200ms (sync by design — the subsequent Flink job startup depends on this)
              const until = Date.now() + 200;
              while (Date.now() < until) { /* spin */ }
            }

            // Recreate and verify it's visible before returning to the client
            spawnSync('docker', [
              'exec', kafkaContainer,
              'kafka-topics.sh', '--create',
              '--topic', topic,
              '--bootstrap-server', 'localhost:9092',
              '--partitions', '1',
              '--replication-factor', '1',
              '--if-not-exists'
            ], { encoding: 'utf8', timeout: 10000 });

            const createDeadline = Date.now() + 10000;
            let created = false;
            while (Date.now() < createDeadline) {
              const describe = spawnSync('docker', [
                'exec', kafkaContainer,
                'kafka-topics.sh', '--describe',
                '--topic', topic,
                '--bootstrap-server', 'localhost:9092'
              ], { encoding: 'utf8', timeout: 5000 });
              if (describe.status === 0) { created = true; break; }
              const until = Date.now() + 200;
              while (Date.now() < until) { /* spin */ }
            }

            if (!created) {
              console.warn(`[Kafka] ⚠️  Topic ${topic} not visible after recreation — Flink may error on subscribe`);
            }
            console.log(`[Kafka] 🗑️  Cleared and recreated topic: ${topic}`);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ ok: true, topic, verified: created }));
          } catch (err) {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: err.message }));
          }
        });
      });

      // ==========================================
      // GET /api/kafka/offset?topic=X[&time=-1] - Get topic end-offset (total msgs)
      // ==========================================
      // Broker-authoritative count of messages on a topic. Used by the Query Runner's
      // drain loop so stopping doesn't depend on the SSE stream (which can flap and
      // silently lose messages on reconnect).
      server.middlewares.use('/api/kafka/offset', (req, res, next) => {
        if (req.method !== 'GET') return next();

        const url = new URL(req.url, 'http://localhost');
        const topic = url.searchParams.get('topic');
        const time = url.searchParams.get('time') || '-1'; // -1 latest, -2 earliest

        if (!topic) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Missing required query param: topic' }));
          return;
        }

        const kafkaContainer = resolveDockerContainerName('kafka');
        if (!kafkaContainer) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Kafka container not found' }));
          return;
        }

        // The Kafka image bundled in docker-compose ships an older GetOffsetShell that
        // accepts --broker-list, not --bootstrap-server. Using the wrong flag returns
        // exit=1 for every call, which silently breaks the drain loop in the Query
        // Runner (brokerOffset stays null → no stop condition fires).
        const result = spawnSync('docker', [
          'exec', kafkaContainer,
          'kafka-run-class.sh', 'kafka.tools.GetOffsetShell',
          '--broker-list', 'localhost:9092',
          '--topic', topic,
          '--time', time
        ], { encoding: 'utf8', timeout: 10000 });

        if (result.status !== 0) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: (result.stderr || result.stdout || 'offset query failed').trim(), topic }));
          return;
        }

        // Output format: topic:partition:offset (one per line)
        let total = 0;
        const partitions = [];
        for (const line of result.stdout.split('\n')) {
          const m = line.match(/^([^:]+):(\d+):(\d+)\s*$/);
          if (!m || m[1] !== topic) continue;
          const offset = parseInt(m[3], 10);
          partitions.push({ partition: parseInt(m[2], 10), offset });
          total += offset;
        }

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, topic, total, partitions }));
      });

      // ==========================================
      // GET /api/kafka/stream?topic=... - Stream Kafka topic via SSE
      // ==========================================
      server.middlewares.use('/api/kafka', (req, res, next) => {
        if (req.method !== 'GET') return next();

        const url = new URL(req.url, 'http://localhost');
        if (url.pathname !== '/stream') return next();

        const topic = url.searchParams.get('topic');
        const fromBeginning = url.searchParams.get('fromBeginning') === '1';

        if (!topic) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Missing required query param: topic' }));
          return;
        }

        const kafkaContainer = resolveDockerContainerName('kafka');
        if (!kafkaContainer) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Kafka container not found (expected a running container whose name includes \"kafka\")' }));
          return;
        }

        res.writeHead(200, {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
          'X-Accel-Buffering': 'no'
        });

        sendSSE(res, { type: 'kafka_started', topic, timestamp: new Date().toISOString() });

        // Send periodic keepalive comments to prevent proxies/browsers from dropping the connection
        const keepalive = setInterval(() => {
          try { res.write(': keepalive\n\n'); } catch { clearInterval(keepalive); }
        }, 15000);

        const consumerArgs = [
          'exec',
          kafkaContainer,
          'kafka-console-consumer.sh',
          '--bootstrap-server',
          'localhost:9092',
          '--topic',
          topic,
          '--consumer-property', 'session.timeout.ms=30000',
          '--consumer-property', 'heartbeat.interval.ms=10000'
        ];

        if (fromBeginning) {
          consumerArgs.push('--from-beginning');
        }

        const consumer = spawn('docker', consumerArgs, {
          cwd: process.cwd(),
          stdio: ['ignore', 'pipe', 'pipe']
        });

        // Write Kafka messages to disk in real-time (JSONL: one JSON per line)
        const kafkaLogPath = join(logsDir, `${topic}.jsonl`);
        writeFileSync(kafkaLogPath, ''); // Clear from previous run
        console.log(`[Kafka] 📝 Streaming messages to ${kafkaLogPath}`);

        let stdoutBuffer = '';
        consumer.stdout.on('data', (data) => {
          stdoutBuffer += data.toString('utf8');

          // Kafka console consumer writes newline-delimited messages.
          let newlineIndex;
          while ((newlineIndex = stdoutBuffer.indexOf('\n')) !== -1) {
            const line = stdoutBuffer.slice(0, newlineIndex).replace(/\r$/, '');
            stdoutBuffer = stdoutBuffer.slice(newlineIndex + 1);

            if (!line) continue;
            sendSSE(res, {
              type: 'kafka_message',
              topic,
              data: line,
              timestamp: new Date().toISOString()
            });
            // Write to disk immediately
            try { appendFileSync(kafkaLogPath, line + '\n'); } catch (_) {}
          }
        });

        let stderrBuffer = '';
        consumer.stderr.on('data', (data) => {
          stderrBuffer += data.toString('utf8');
          const trimmed = stderrBuffer.trim();
          if (!trimmed) return;

          // Emit as a single error event; keep connection alive so the UI sees it.
          sendSSE(res, {
            type: 'kafka_error',
            topic,
            data: trimmed,
            timestamp: new Date().toISOString()
          });
          stderrBuffer = '';
        });

        consumer.on('close', (code) => {
          clearInterval(keepalive);
          sendSSE(res, {
            type: 'kafka_closed',
            topic,
            exit_code: code,
            timestamp: new Date().toISOString()
          });
          res.end();
        });

        consumer.on('error', (error) => {
          clearInterval(keepalive);
          sendSSE(res, {
            type: 'kafka_error',
            topic,
            data: `Failed to start Kafka consumer: ${error.message}`,
            timestamp: new Date().toISOString()
          });
          res.end();
        });

        req.on('close', () => {
          clearInterval(keepalive);
          try {
            consumer.kill('SIGTERM');
          } catch {
            // ignore
          }
        });
      });

      // ==========================================
      // POST /api/results/save - Save query results to local file
      // ==========================================
      server.middlewares.use('/api/results/save', async (req, res, next) => {
        if (req.method !== 'POST') return next();

        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', () => {
          try {
            const { filename, data } = JSON.parse(body);
            const safeName = filename.replace(/[/\\:*?"<>|]/g, '_');
            const finalName = safeName.endsWith('.json') ? safeName : safeName + '.json';
            const filePath = join(resultsDir, finalName);
            writeFileSync(filePath, JSON.stringify(data, null, 2));
            console.log(`[Results] 💾 Saved: ${finalName}`);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: true, path: `results/${finalName}` }));
          } catch (error) {
            console.error('[Results] Error saving:', error.message);
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: error.message }));
          }
        });
      });

      // ==========================================
      // POST /api/results/append - Append a single JSON line to a results file (JSONL)
      // ==========================================
      server.middlewares.use('/api/results/append', (req, res, next) => {
        if (req.method !== 'POST') return next();

        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', () => {
          try {
            const { filename, line, clear } = JSON.parse(body);
            const safeName = filename.replace(/[/\\:*?"<>|]/g, '_');
            const filePath = join(resultsDir, safeName);
            if (clear) {
              writeFileSync(filePath, '');
            } else {
              appendFileSync(filePath, line + '\n');
            }
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end('{"ok":true}');
          } catch (error) {
            console.error('[Results] Append error:', error.message);
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: error.message }));
          }
        });
      });

      // ==========================================
      // POST /api/metrics/save - Save metrics to dedicated folder + CSV summary
      // ==========================================
      server.middlewares.use('/api/metrics/save', async (req, res, next) => {
        if (req.method !== 'POST') return next();

        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', () => {
          try {
            const { filename, csvRow, detailData } = JSON.parse(body);

            // 1. Save detailed JSON
            const safeName = filename.replace(/[/\\:*?"<>|]/g, '_');
            const jsonName = safeName.endsWith('.json') ? safeName : safeName + '.json';
            const jsonPath = join(metricsDir, jsonName);
            writeFileSync(jsonPath, JSON.stringify(detailData, null, 2));

            // 2. Append to summary.csv
            const csvPath = join(metricsDir, 'summary.csv');
            const csvColumns = [
              'query_title', 'timestamp', 'duration_s', 'message_count',
              'llm_model', 'has_window', 'has_grayscale',
              'resize_width', 'resize_height',
              'brand_accuracy', 'color_accuracy', 'plate_accuracy',
              'avg_llm_time_ms', 'avg_e2e_ms',
              'avg_decode_ms', 'avg_resize_ms', 'avg_llm_op_ms', 'avg_grayscale_ms',
              'pipeline_nodes'
            ];

            const headerNeeded = !existsSync(csvPath);
            let csvLine = '';
            if (headerNeeded) {
              csvLine += csvColumns.join(',') + '\n';
            }
            csvLine += csvColumns.map(col => {
              const val = csvRow[col];
              if (val === null || val === undefined || val === '') return '';
              const str = String(val);
              // Quote values that contain commas or quotes
              if (str.includes(',') || str.includes('"') || str.includes('\n')) {
                return `"${str.replace(/"/g, '""')}"`;
              }
              return str;
            }).join(',') + '\n';
            appendFileSync(csvPath, csvLine);

            console.log(`[Metrics] 📊 Saved: ${jsonName} + summary.csv`);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: true, jsonPath: `results/metrics/${jsonName}`, csvPath: 'results/metrics/summary.csv' }));
          } catch (error) {
            console.error('[Metrics] Error saving:', error.message);
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: error.message }));
          }
        });
      });

      // ==========================================
      // POST /api/sender/run - Run a frame-sender Python script to completion
      // ==========================================
      // Used by the Query Runner's "Run Selected" queue to fire send_video.py
      // (or a volleyball equivalent) automatically after each pipeline is ready.
      server.middlewares.use('/api/sender/run', (req, res, next) => {
        if (req.method !== 'POST') return next();

        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', () => {
          try {
            const { script, cwd } = JSON.parse(body || '{}');
            const scriptRel = script || 'running/Topics/Cars/Data/send_video.py';
            // Default cwd = the sender script's directory (so relative paths like cars-me/04/... resolve).
            const cwdRel = cwd || scriptRel.substring(0, scriptRel.lastIndexOf('/')) || '.';
            const scriptAbs = join(process.cwd(), scriptRel);
            const cwdAbs = join(process.cwd(), cwdRel);

            if (!existsSync(scriptAbs)) {
              res.writeHead(404, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: `Sender script not found: ${scriptRel}` }));
              return;
            }

            // Allow overriding the interpreter — useful when the auto-detected venv is a
            // Windows .exe but Node is running in WSL (or vice-versa).
            const senderPython = process.env.SENDER_PYTHON || PYTHON_EXE;
            console.log(`[Sender] ▶️  Running ${scriptRel} (python=${senderPython}, cwd=${cwdRel})`);
            const startTime = Date.now();
            const proc = spawn(senderPython, [scriptAbs], {
              cwd: cwdAbs,
              stdio: ['ignore', 'pipe', 'pipe']
            });

            let stdoutTail = '';
            let stderrTail = '';
            const MAX_TAIL = 8000;
            proc.stdout.on('data', d => {
              stdoutTail = (stdoutTail + d.toString()).slice(-MAX_TAIL);
            });
            proc.stderr.on('data', d => {
              stderrTail = (stderrTail + d.toString()).slice(-MAX_TAIL);
            });

            let settled = false;
            proc.on('close', code => {
              if (settled) return;
              settled = true;
              const duration = ((Date.now() - startTime) / 1000).toFixed(2);
              console.log(`[Sender] ${code === 0 ? '✅' : '❌'} ${scriptRel} (${senderPython}) exited code=${code} duration=${duration}s`);
              if (stdoutTail.trim()) console.log(`[Sender] stdout tail:\n${stdoutTail.trim()}`);
              if (stderrTail.trim()) console.log(`[Sender] stderr tail:\n${stderrTail.trim()}`);
              res.writeHead(200, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({
                returncode: code,
                duration_s: parseFloat(duration),
                python: senderPython,
                stdout_tail: stdoutTail,
                stderr_tail: stderrTail
              }));
            });

            proc.on('error', err => {
              if (settled) return;
              settled = true;
              console.error(`[Sender] ❌ Spawn error (${senderPython}): ${err.message}`);
              res.writeHead(500, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: err.message, python: senderPython }));
            });
            // NOTE: no `req.on('close', kill)` — Vite's middleware pipeline can fire that
            // before the sender is actually done on Windows, killing Python with SIGTERM
            // (which shows up as exit code `null` in child_process).
          } catch (err) {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: err.message }));
          }
        });
      });

      // ==========================================
      // POST /api/plots/render - Render thesis PNG plots from metrics/<slug>.json
      // ==========================================
      server.middlewares.use('/api/plots/render', (req, res, next) => {
        if (req.method !== 'POST') return next();

        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', () => {
          try {
            const { slug } = JSON.parse(body);
            if (!slug) {
              res.writeHead(400, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: 'Missing required field: slug' }));
              return;
            }
            const safeSlug = slug.replace(/[/\\:*?"<>|]/g, '_');
            const result = spawnSync(PYTHON_EXE, ['scripts/render_thesis_plots.py', safeSlug], {
              cwd: process.cwd(),
              encoding: 'utf8',
              timeout: 120000
            });
            if (result.status !== 0) {
              console.error(`[Plots] Render failed for ${safeSlug}: ${result.stderr || result.stdout}`);
              res.writeHead(500, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: (result.stderr || result.stdout || 'Render failed').trim() }));
              return;
            }
            console.log(`[Plots] 📈 Rendered: results/plots/${safeSlug}/`);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ ok: true, slug: safeSlug, outputDir: `results/plots/${safeSlug}` }));
          } catch (error) {
            console.error('[Plots] Error:', error.message);
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: error.message }));
          }
        });
      });
    }
  };
}

// Helper: Send SSE message
function sendSSE(res, data) {
  res.write(`data: ${JSON.stringify(data)}\n\n`);
}

// Helper: Simple hash function
function hashCode(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return hash;
}

function extractKafkaTopicFromScript(script) {
  // Matches: .set_topic("output-topic")
  const topicMatches = [...script.matchAll(/\.set_topic\(\s*["']([^"']+)["']\s*\)/g)];
  if (topicMatches.length === 0) return null;
  return topicMatches[topicMatches.length - 1][1];
}

function extractKafkaBootstrapFromScript(script) {
  // Matches: .set_bootstrap_servers("kafka:9093")
  const match = script.match(/\.set_bootstrap_servers\(\s*["']([^"']+)["']\s*\)/);
  return match ? match[1] : null;
}

function listRunningFlinkJobs() {
  try {
    const jobmanager = resolveDockerContainerName('jobmanager') || 'jobmanager';
    const result = spawnSync('docker', [
      'exec', jobmanager, 'flink', 'list', '--running'
    ], { encoding: 'utf8', timeout: 10000 });

    const text = `${result.stdout || ''}\n${result.stderr || ''}`;
    const ids = text.match(/\b[a-f0-9]{32}\b/g) || [];
    return [...new Set(ids)];
  } catch {
    return [];
  }
}

function cancelRunningFlinkJobs(skipJobIds = []) {
  const skip = new Set(skipJobIds.filter(Boolean));
  const jobmanager = resolveDockerContainerName('jobmanager') || 'jobmanager';
  const cancelled = [];
  for (const jobId of listRunningFlinkJobs()) {
    if (skip.has(jobId)) continue;
    try {
      const result = spawnSync('docker', [
        'exec', jobmanager, 'flink', 'cancel', jobId
      ], { encoding: 'utf8', timeout: 15000 });
      if (result.status === 0) {
        cancelled.push(jobId);
      } else {
        console.warn(`[Execute] Could not cancel Flink job ${jobId}: ${(result.stderr || result.stdout || '').trim()}`);
      }
    } catch (err) {
      console.warn(`[Execute] Error cancelling Flink job ${jobId}: ${err.message}`);
    }
  }
  return cancelled;
}

function resolveDockerContainerName(nameFragment) {
  try {
    const result = spawnSync('docker', ['ps', '--format', '{{.Names}}'], { encoding: 'utf8' });
    if (result.status !== 0) return null;

    const names = result.stdout
      .split(/\r?\n/)
      .map(s => s.trim())
      .filter(Boolean);

    const exact = names.find(n => n === nameFragment);
    if (exact) return exact;

    return names.find(n => n.includes(nameFragment)) || null;
  } catch {
    return null;
  }
}
