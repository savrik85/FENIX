from fastapi import FastAPI
from datetime import datetime

app = FastAPI(
    title="FENIX Eagle - Tender Monitoring Agent",
    description="AI-powered tender monitoring and scraping service",
    version="1.0.0"
)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "fenix-eagle",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    return {
        "message": "FENIX Eagle - AI Scrape Service",
        "status": "ready",
        "features": [
            "Tender monitoring",
            "AI-powered scraping", 
            "SAM.gov integration",
            "Dodge Construction monitoring"
        ]
    }

@app.get("/scrape/sources")
async def get_sources():
    return {
        "sources": [
            {
                "id": "sam.gov",
                "name": "SAM.gov",
                "description": "US Government procurement opportunities",
                "status": "available"
            },
            {
                "id": "dodge",
                "name": "Dodge Construction",
                "description": "Construction project leads",
                "status": "coming_soon"
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)