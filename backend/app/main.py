from fastapi import FastAPI

app = FastAPI()


# Rota simples para conferir se o servidor está no ar.
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
