from fastapi import FastAPI

from app.api import auth, users

app = FastAPI(title="AuthHub")

app.include_router(auth.router)
app.include_router(users.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
