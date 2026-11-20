import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.browser_engine import close_browser, init_browser
from backend.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_browser()
    yield
    await close_browser()


app = FastAPI(title="Goofish Live Search", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    from backend.config import SERVER_PORT

    uvicorn.run("backend.main:app", host="0.0.0.0", port=SERVER_PORT, reload=False)
