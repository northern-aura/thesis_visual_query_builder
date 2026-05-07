# ReactFlow Query Builder - Quick Start Guide

## 🚀 Single Command Setup

This application now auto-starts both the frontend and backend with a **single command**!

---

## Prerequisites

Make sure you have these installed:
- **Node.js** (v16 or higher)
- **Python** (v3.8 or higher)
- **Docker Desktop** (running)

---

## First-Time Setup

### 1. Install Frontend Dependencies
```bash
npm install
```

### 2. Install Backend Dependencies
```bash
cd backend
pip install -r requirements.txt
cd ..
```

### 3. Start Docker Containers (if needed)
Make sure Docker Desktop is running, then navigate to the Docker directory:
```bash
cd running/Docker
docker-compose -f env-compose.yml up -d
cd ../..
```

This starts:
- **Flink JobManager** (localhost:8081)
- **Flink TaskManager**
- **Kafka** (localhost:9092)
- **Zookeeper** (localhost:2181)

---

## Running the Application

### Single Command - Runs Everything!
```bash
npm run dev
```

**What happens:**
1. ✅ Vite dev server starts on `localhost:5173`
2. ✅ Python backend auto-starts on `localhost:3001`
3. ✅ Frontend automatically proxies `/api` requests to backend
4. ✅ Both logs appear in the same terminal

**You'll see:**
```
🐍 Starting Python backend server...
[Backend] INFO:     Uvicorn running on http://0.0.0.0:3001
✅ Python backend ready on http://localhost:3001
📚 API docs: http://localhost:3001/docs

  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
```

---

## Using the Application

### 1. **Build Your Query Pipeline**
- Drag and drop nodes from the sidebar
- Connect them to create your data pipeline
- Configure parameters for each node

### 2. **Add Custom Nodes** (Optional)
- Click the **"Custom"** card in the sidebar (gear icon)
- Fill in:
  - Label, Icon, Color
  - Parameters (format: `id|name|label|type`)
  - Python class code
  - Method name
- Save and use it like any other node!

### 3. **Export Your Work**
Click **Menu** (bottom right) → Choose option:
- **Export JSON** - Save pipeline structure
- **Export Python** - Get Python script
- **Batch Export** - Generate 10 variations
- **Export Custom Nodes** - Save your custom nodes
- **Screenshot** - Capture visual

### 4. **Execute Python Scripts** 🆕
Click **Menu** → **▶ Execute Python**

**What happens:**
1. Script is generated from your pipeline
2. Backend saves it to `/scripts/` directory
3. Backend checks Docker containers (auto-starts if needed)
4. Script executes inside Flink container
5. **Results Panel** opens at the bottom showing:
   - Real-time stdout/stderr
   - Execution status
   - Duration and exit code
   - Download logs option

---

## Project Structure

```
project/
├── src/                    # React frontend
│   ├── components/
│   │   ├── custom-nodes/  # Custom node modal
│   │   ├── execution/     # Results panel
│   │   ├── export/        # Export & execute buttons
│   │   └── nodes/         # Node components
│   └── services/          # API clients (backend, SSE)
│
├── backend/               # Python FastAPI backend
│   ├── main.py           # Entry point (auto-started by Vite)
│   ├── api/              # API routes
│   ├── services/         # Docker, execution, storage
│   └── models/           # Data schemas
│
├── vite-plugins/         # Custom Vite plugins
│   └── backend-launcher.js  # Auto-starts Python backend
│
├── scripts/              # Generated execution scripts (auto-created)
├── running/Docker/       # Docker compose files
└── vite.config.js        # Vite config with backend launcher
```

---

## API Documentation

While the app is running, visit:
- **Swagger UI:** http://localhost:3001/docs
- **ReDoc:** http://localhost:3001/redoc

---

## Troubleshooting

### Backend won't start
**Error:** `Python backend failed to start`

**Solution:**
1. Make sure Python is installed: `python --version`
2. Install backend dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   cd ..
   ```

### Docker errors during execution
**Error:** `jobmanager container not found`

**Solution:**
1. Make sure Docker Desktop is running
2. Start containers manually:
   ```bash
   cd running/Docker
   docker-compose -f env-compose.yml up -d
   ```

### Port already in use
**Error:** `Port 5173 already in use` or `Port 3001 already in use`

**Solution:**
1. Kill existing processes on those ports
2. Or change ports in `vite.config.js`:
   ```javascript
   server: {
     port: 9000  // Change frontend port
   }
   ```
3. And `backend/config.py`:
   ```python
   BACKEND_PORT = 3002  # Change backend port
   ```

### Can't see execution results
**Solution:**
1. Check browser console for errors
2. Verify backend is running: http://localhost:3001/health
3. Check Docker containers: `docker ps`

---

## Features Summary

✅ **Custom Nodes** - Create and save your own reusable nodes
✅ **Export Pipeline** - JSON, Python, or batch variations
✅ **Execute Scripts** - Run Python scripts with Flink
✅ **Real-time Results** - See execution output as it happens
✅ **Docker Integration** - Auto-starts Flink/Kafka if needed
✅ **Execution History** - View past runs and download logs
✅ **Single Command** - Everything starts with `npm run dev`

---

## Next Steps

1. **Try it out:** Build a simple pipeline and execute it
2. **Create custom nodes:** Add your own processing logic
3. **Share pipelines:** Export JSON and share with teammates
4. **Monitor Flink:** Visit http://localhost:8081 for Flink dashboard

---

## Need Help?

- Check the API docs: http://localhost:3001/docs
- View Flink dashboard: http://localhost:8081
- Backend logs appear in the same terminal with `[Backend]` prefix
- Frontend logs appear in browser console

Enjoy building! 🎉
