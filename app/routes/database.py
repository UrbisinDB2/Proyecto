from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models.parsed_query import ParsedQuery

router = APIRouter()

def

@router.post("/", response_class=JSONResponse)
async def run_query(query: ParsedQuery):
    op = query.op

    if op == 0:
        pass
    elif op == 1:
        pass
    elif op == 2:
        pass
    elif op == 3:
        pass
    elif op == 4:
        pass