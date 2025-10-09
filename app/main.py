from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok", "message": "Minimal API working"}

@app.get("/health")
def health():
    return {"status": "healthy"}
