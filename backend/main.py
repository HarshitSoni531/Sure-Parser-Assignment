from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from routers import authentication, user, statement  # all relative

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sure Financial - Credit Card Parser", version="1.0.0")

ALLOWED_ORIGINS = [
    "https://sure-parser-assignment.vercel.app",   # Vercel prod
    "http://localhost:5173",                       # Vite dev
    "http://127.0.0.1:5173",
]


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(authentication.router)
app.include_router(user.router)
app.include_router(statement.router)

# Health check
@app.get("/healthz")
def health():
    return {"status": "ok"}

