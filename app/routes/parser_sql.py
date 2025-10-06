from fastapi import APIRouter

from app.models.query import Query

router = APIRouter()


@router.post("/", response_model=Query)
def parse(query: Query):
    q = query.text

    q.split(" ")

    print(q)
