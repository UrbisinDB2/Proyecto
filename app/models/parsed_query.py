from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class ParsedQuery(BaseModel):
    op: int
    table: Optional[str] = None
    columns: Optional[List[str]] = None
    where: Optional[Dict[str, Any]] = None
    file: Optional[str] = None
    index: Optional[Dict[str, Any]] = None
    values: Optional[List[List[Any]]] = None
