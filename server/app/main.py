from fastapi import FastAPI
from app.api.router import api_router
import uvicorn


app = FastAPI(title="AI Agent Server", version="0.1.0")
app.include_router(api_router, prefix="/api")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)