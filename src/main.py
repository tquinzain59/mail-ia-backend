from fastapi import FastAPI
from dotenv import load_dotenv
from src.webhooks.mailgun import router as mailgun_router

load_dotenv()
app = FastAPI(title="Mail IA Backend", version="0.1.0")

@app.get("/health")
def health():
    return {"status": "ok"}

# Webhook inbound provider (Mailgun ici, mais interchangeable)
app.include_router(mailgun_router, prefix="/webhooks/mailgun", tags=["mailgun"])

@app.get("/")
def root():
    return {
        "name": "Mail IA Backend",
        "version": "0.1.0",
        "health": "/health",
        "docs": "/docs"
    }