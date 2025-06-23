from fastapi import FastAPI
from datetime import datetime

app = FastAPI(title="FENIX BOLT")

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "fenix-bolt", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
