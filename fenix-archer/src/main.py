from datetime import datetime

from fastapi import FastAPI


app = FastAPI(title="FENIX ARCHER")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "fenix-archer",
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8008)
