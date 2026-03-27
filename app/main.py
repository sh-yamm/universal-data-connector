# Entry point — spins up FastAPI and wires in the two routers
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from app.routers import health, data
from app.utils.logging import configure_logging

configure_logging()

app = FastAPI(title="Universal Data Connector")

# /health lives in health.py, all /api/* routes live in data.py
app.include_router(health.router)
app.include_router(data.router)


@app.get("/")
def root():
    return RedirectResponse(url="/docs")
