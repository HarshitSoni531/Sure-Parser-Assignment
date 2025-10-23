# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from routers import authentication, user, statement

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sure Financial - Credit Card Parser", version="1.0.0")

# --- CORS ---
# Explicitly allow your stable prod + local dev,
# and allow ALL Vercel preview URLs for this project via regex.
ALLOWED_ORIGINS = [
    "https://sure-parser-assignment.vercel.app",  # Vercel stable prod (if you keep it)
    "http://localhost:5173",                      # Vite dev
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    # Matches preview deployments like:
    # https://sure-parser-assignment-xxxxx.vercel.app
    # and also the base without suffix.
    allow_origin_regex=r"^https://sure-parser-assignment(-[a-z0-9-]+)?\.vercel\.app$",
    allow_credentials=True,   # ok since we are NOT using "*"
    allow_methods=["*"],
    allow_headers=["*"],      # includes Authorization, Content-Type, etc.
)

# Routers
app.include_router(authentication.router)
app.include_router(user.router)
app.include_router(statement.router)

# Health check
@app.get("/healthz")
def health():
    return {"status": "ok"}
