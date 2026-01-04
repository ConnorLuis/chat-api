from fastapi import FastAPI

from src.app.api.routes_chat import router as chat_router
from src.app.core.logging import install_logging_middleware

app = FastAPI()
install_logging_middleware(app)

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(chat_router)