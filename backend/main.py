import logging
import os
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.browser_engine import close_browser, init_browser
from backend.cache import init_cache_db
from backend.deals import init_deals_db
from backend.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_cache_db()
    init_deals_db()
    await init_browser()
    yield
    await close_browser()


app = FastAPI(title="Goofish Live Search", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1212", "http://127.0.0.1:1212", "http://0.0.0.0:1212"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Requested-With"],
)

app.include_router(router)

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    from backend.config import SERVER_PORT

    uvicorn.run("backend.main:app", host="0.0.0.0", port=SERVER_PORT, reload=False)
