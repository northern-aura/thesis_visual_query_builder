/**
 * Vite plugin to auto-start Python backend server.
 * Spawns the FastAPI backend as a child process when dev server starts.
 */
import { spawn } from 'child_process';
import path from 'path';

export function backendLauncher() {
  let backendProcess = null;
  let isBackendReady = false;

  return {
    name: 'backend-launcher',

    configureServer(server) {
      // Start Python backend when Vite dev server starts
      const backendPath = path.join(process.cwd(), 'backend', 'main.py');

      console.log('\n🐍 Starting Python backend server...');

      backendProcess = spawn('python', [backendPath], {
        cwd: process.cwd(),
        stdio: ['ignore', 'pipe', 'pipe']
      });

      // Handle backend stdout
      backendProcess.stdout.on('data', (data) => {
        const output = data.toString();

        // Check if backend is ready
        if (output.includes('Uvicorn running on') || output.includes('Application startup complete')) {
          if (!isBackendReady) {
            isBackendReady = true;
            console.log('✅ Python backend ready on http://localhost:3001');
            console.log('📚 API docs: http://localhost:3001/docs\n');
          }
        }

        // Print backend logs with prefix
        output.split('\n').forEach(line => {
          if (line.trim()) {
            console.log(`[Backend] ${line}`);
          }
        });
      });

      // Handle backend stderr
      backendProcess.stderr.on('data', (data) => {
        const output = data.toString();
        output.split('\n').forEach(line => {
          if (line.trim()) {
            console.error(`[Backend Error] ${line}`);
          }
        });
      });

      // Handle backend exit
      backendProcess.on('exit', (code, signal) => {
        if (code !== null && code !== 0) {
          console.error(`\n❌ Backend exited with code ${code}`);
        } else if (signal) {
          console.log(`\n🛑 Backend stopped (${signal})`);
        }
        backendProcess = null;
        isBackendReady = false;
      });

      // Handle backend errors
      backendProcess.on('error', (err) => {
        console.error('\n❌ Failed to start Python backend:', err.message);
        console.error('Make sure Python is installed and accessible in your PATH');
        backendProcess = null;
      });

      // Health check endpoint
      server.middlewares.use('/api/backend-health', (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: isBackendReady ? 'ready' : 'starting',
          backendRunning: backendProcess !== null
        }));
      });
    },

    closeBundle() {
      // Kill backend when Vite closes (production build)
      if (backendProcess) {
        console.log('\n🛑 Stopping Python backend...');
        backendProcess.kill('SIGTERM');
        backendProcess = null;
      }
    },

    buildEnd() {
      // Kill backend when Vite dev server closes
      if (backendProcess) {
        console.log('\n🛑 Stopping Python backend...');
        backendProcess.kill('SIGTERM');
        backendProcess = null;
      }
    }
  };
}
