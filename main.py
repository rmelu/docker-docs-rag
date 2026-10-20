"""Docker Docs RAG - API FastAPI.

Avvio:  uvicorn main:app --reload --port 8005
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from rag import rispondi

BASE = Path(__file__).parent
app = FastAPI(title="Docker Docs RAG")


class Domanda(BaseModel):
    domanda: str = Field(min_length=3)
    k: int = Field(default=4, ge=1, le=10)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE / "static" / "index.html")


@app.post("/ask")
def ask(body: Domanda):
    try:
        return rispondi(body.domanda, body.k)
    except RuntimeError:
        raise HTTPException(status_code=502, detail="Il servizio LLM non ha risposto")