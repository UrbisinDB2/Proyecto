from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.routes import parser_sql, database

app = FastAPI(
    title="Mini Database Manager",
    version="1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", name="root")
async def root():
    return JSONResponse(status_code=200, content="Hello from Mini Database Manager")

app.include_router(parser_sql.router, prefix="/parser")
app.include_router(database.router, prefix="/database")