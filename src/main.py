from fastapi import FastAPI

from api import auth, projects

app = FastAPI(title="Project Dashboard")

app.include_router(auth.router)
app.include_router(projects.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
