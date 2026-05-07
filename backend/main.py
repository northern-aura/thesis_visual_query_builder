"""FastAPI application for ReactFlow Query Builder backend."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from api.routes import router
from config import BACKEND_HOST, BACKEND_PORT

# Create FastAPI app
app = FastAPI(
    title="ReactFlow Query Builder API",
    description="Backend API for executing PyFlink scripts with real-time streaming",
    version="1.0.0"
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "ReactFlow Query Builder API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    print(f"Starting backend server on {BACKEND_HOST}:{BACKEND_PORT}")
    print(f"API documentation available at http://{BACKEND_HOST}:{BACKEND_PORT}/docs")

    uvicorn.run(
        "main:app",
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        reload=True,
        log_level="info"
    )
