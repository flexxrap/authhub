from fastapi import FastAPI

from app.api import auth, notifications, users

app = FastAPI(title="AuthHub")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(notifications.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
