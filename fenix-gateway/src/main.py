from fastapi import FastAPI
from datetime import datetime

app = FastAPI(
    title="FENIX Gateway - API Gateway",
    description="Central API gateway for FENIX microservices",
    version="1.0.0"
)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "fenix-gateway",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    return {
        "message": "FENIX Gateway - API Gateway",
        "services": {
            "eagle": "http://eagle:8001",
            "archer": "http://archer:8002", 
            "oracle": "http://oracle:8003",
            "bolt": "http://bolt:8004",
            "shield": "http://shield:8005",
            "core": "http://core:8006"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)