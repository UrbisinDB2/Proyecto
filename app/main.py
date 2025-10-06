from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routes import parser_sql, database

app = FastAPI(
    title="Mini Database Manager",
    version="1.0",
)

@app.get("/", name="root")
async def root():
    return JSONResponse(status_code=200, content="Hello from Mini Database Manager")

app.include_router(parser_sql.router, prefix="/parser")
app.include_router(database.router, prefix="/database")