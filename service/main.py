from fastapi import FastAPI

app = FastAPI(title="Proton-X LLM Service")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "proton-x-llm", "version": "0.1.0"}
