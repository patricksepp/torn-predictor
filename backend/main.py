from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, predict, data, subscription, admin
from config import settings

app = FastAPI(title="Torn Battle Stats Predictor API", version="0.1.0")

ALLOWED_ORIGINS = [
    "https://www.torn.com",            # userscript
    "https://torn.com",
    "https://torn-predictor.vercel.app",
    "http://localhost:3000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(predict.router, prefix="/api/predict", tags=["predict"])
app.include_router(data.router, prefix="/api/data", tags=["data"])
app.include_router(subscription.router, prefix="/api/subscription", tags=["subscription"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/cron/check-payments")
async def cron_check_payments(secret: str = Query(...)):
    """
    Called by an external cron service (e.g. cron-job.org) every hour.
    Scans our Torn account events for new xanax payments and applies them.
    Protected by a static secret key set in CRON_SECRET env var.
    """
    if not settings.cron_secret or secret != settings.cron_secret:
        raise HTTPException(403, "Invalid cron secret")

    from services.payments import check_and_apply_payments
    applied = await check_and_apply_payments()
    return {"applied": len(applied), "payments": applied}
