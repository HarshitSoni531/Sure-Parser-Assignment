from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import authentication, user, statement  # all relative

# create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sure Financial - Credit Card Parser", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(authentication.router)
app.include_router(user.router)
app.include_router(statement.router)


@app.get("/healthz")
def health():
    return {"status": "ok"}
