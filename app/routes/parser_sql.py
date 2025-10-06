from fastapi import APIRouter
from fastapi.responses import JSONResponse
import re
from typing import List, Dict, Any, Optional

from app.models.query import Query

router = APIRouter()

def normalize_type(raw_type: str) -> str:
    raw_type = raw_type.strip().lower()

    # varchar[n]
    if raw_type.startswith("varchar["):
        m = re.search(r"\[(\d+)\]", raw_type)
        return f"varchar({m.group(1)})" if m else "varchar"

    # array[tipo]
    if raw_type.startswith("array["):
        m = re.search(r"\[([a-z0-9_]+)\]", raw_type)
        return f"array({m.group(1)})" if m else "array"

    # simples
    if raw_type in ("int", "float", "date", "string"):
        return raw_type

    return raw_type

def _parse_literal(s: str):
    s = s.strip()
    if len(s) >= 2 and ((s[0] == s[-1] == "'") or (s[0] == s[-1] == '"')):
        return s[1:-1]
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", s):
        return float(s) if "." in s else int(s)
    # true/false/null
    low = s.lower()
    if low == "true": return True
    if low == "false": return False
    if low == "null": return None
    return s

def _split_by_commas_outside_brackets(text: str) -> List[str]:
    parts, cur, level = [], [], 0
    for ch in text:
        if ch == "[":
            level += 1
        elif ch == "]":
            level -= 1
        elif ch == "," and level == 0:
            parts.append("".join(cur).strip())
            cur = []
            continue
        cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return parts

def _split_csv_top(text: str) -> List[str]:
    parts, cur = [], []
    lvl_round = lvl_square = 0
    in_s = in_d = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "'" and not in_d:
            in_s = not in_s
            cur.append(ch)
        elif ch == '"' and not in_s:
            in_d = not in_d
            cur.append(ch)
        elif in_s or in_d:
            cur.append(ch)
        else:
            if ch == "(":
                lvl_round += 1; cur.append(ch)
            elif ch == ")":
                lvl_round -= 1; cur.append(ch)
            elif ch == "[":
                lvl_square += 1; cur.append(ch)
            elif ch == "]":
                lvl_square -= 1; cur.append(ch)
            elif ch == "," and lvl_round == 0 and lvl_square == 0:
                parts.append("".join(cur).strip()); cur = []
            else:
                cur.append(ch)
        i += 1
    if cur:
        parts.append("".join(cur).strip())
    return parts

def _parse_point_tuple(s: str):
    s = s.strip()
    if s.startswith("(") and s.endswith(")"):
        inner = s[1:-1].strip()
        parts = [p.strip() for p in inner.split(",")]
        if len(parts) == 2:
            # lat, lon (o x, y)
            a = _parse_literal(parts[0])
            b = _parse_literal(parts[1])
            return (a, b)
    return s  # si no es "(a,b)", devuélvelo crudo

def parse_create(sql: str) -> Dict[str, Any]:
    # CREATE TABLE <tabla> (<cols>)
    m = re.match(
        r"^\s*CREATE\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*$",
        sql, flags=re.IGNORECASE | re.DOTALL
    )
    if not m:
        raise ValueError("CREATE TABLE inválido")

    table_name = m.group(1)
    columns_part = m.group(2)

    columns_raw = _split_by_commas_outside_brackets(columns_part)
    columns: List[Dict[str, Any]] = []
    for coldef in columns_raw:
        tokens = [t for t in coldef.strip().split() if t]
        if len(tokens) < 2:
            continue
        name = tokens[0]
        col_type = tokens[1]
        columns.append({
            "name": name.lower(),
            "type": normalize_type(col_type.lower()),
        })

    return {
        "op": 0,
        "table": table_name,
        "columns": columns,
    }

def parse_select(sql: str) -> Dict[str, Any]:
    # SELECT cols FROM table [WHERE cond]
    m = re.match(
        r"^\s*SELECT\s+(?P<cols>.+?)\s+FROM\s+(?P<table>[A-Za-z_][A-Za-z0-9_]*)"
        r"(?:\s+WHERE\s+(?P<cond>.+))?$",
        sql, flags=re.IGNORECASE | re.DOTALL
    )
    if not m:
        raise ValueError("SELECT inválido")

    cols_raw = m.group("cols").strip()
    table = m.group("table")
    cond = (m.group("cond") or "").strip()

    columns = ["*"] if cols_raw == "*" else [c.strip() for c in cols_raw.split(",") if c.strip()]
    parsed: Dict[str, Any] = {
        "op": 1,
        "columns": columns,
        "table": table,
    }

    if not cond:
        return parsed

    # WHERE soportados
    m_eq = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", cond, flags=re.IGNORECASE)
    if m_eq:
        field = m_eq.group(1)
        value = _parse_literal(m_eq.group(2))
        parsed["where"] = {"type": "eq", "field": field, "value": value}
        return parsed

    m_between = re.match(
        r"^([A-Za-z_][A-Za-z0-9_]*)\s+BETWEEN\s+(.+?)\s+AND\s+(.+)$",
        cond, flags=re.IGNORECASE | re.DOTALL
    )
    if m_between:
        field = m_between.group(1)
        lo = _parse_literal(m_between.group(2))
        hi = _parse_literal(m_between.group(3))
        parsed["where"] = {"type": "between", "field": field, "from": lo, "to": hi}
        return parsed

    m_in_circle = re.match(
        r"^([A-Za-z_][A-Za-z0-9_]*)\s+IN\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)$",
        cond, flags=re.IGNORECASE | re.DOTALL
    )
    m_in_circle = re.match(
        r"^([A-Za-z_][A-Za-z0-9_]*)\s+IN\s*\(\s*(.+)\s*\)$",
        cond, flags=re.IGNORECASE | re.DOTALL
    )
    if m_in_circle:
        field = m_in_circle.group(1)
        inner = m_in_circle.group(2)
        parts = _split_csv_top(inner)
        if len(parts) == 2:
            point_raw = parts[0].strip()
            radius_raw = parts[1].strip()
            point = _parse_point_tuple(point_raw)
            radius = _parse_literal(radius_raw)
            parsed["where"] = {
                "type": "in_circle",
                "field": field,
                "point": point,  # p.ej. (-12.05, -77.04)
                "radius": radius  # p.ej. 3.5
            }
            return parsed

    parsed["where"] = {"type": "raw", "expr": cond}
    return parsed

def parse_insert(sql: str) -> Dict[str, Any]:
    # con columnas
    m = re.match(
        r"^\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((.+?)\)\s*VALUES\s*\((.+)\)\s*$",
        sql, flags=re.IGNORECASE | re.DOTALL
    )
    cols: Optional[List[str]] = None
    if m:
        table = m.group(1)
        cols = [c.strip() for c in _split_csv_top(m.group(2))]
        vals_raw = m.group(3)
    else:
        # sin columnas
        m2 = re.match(
            r"^\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\s*VALUES\s*\((.+)\)\s*$",
            sql, flags=re.IGNORECASE | re.DOTALL
        )
        if not m2:
            raise ValueError("INSERT inválido")
        table = m2.group(1)
        vals_raw = m2.group(2)

    # ======================
    # Soporte para objetos { ... }
    # ======================
    # ejemplo: {12, 'ASD', '2025/06/15', [-123213.123123]}, {13, 'KFC', ...}
    objects = []
    buf, level_curly = [], 0
    for ch in vals_raw:
        if ch == "{":
            level_curly += 1
            if level_curly == 1:
                buf = []  # iniciar nuevo objeto
                continue
        elif ch == "}":
            level_curly -= 1
            if level_curly == 0:
                obj_str = "".join(buf).strip()
                if obj_str:
                    objects.append(obj_str)
                continue
        if level_curly >= 1:
            buf.append(ch)

    # Si no se detectaron objetos {}, tratamos como inserción simple
    if not objects:
        values = [_parse_literal(v) for v in _split_csv_top(vals_raw)]
        return {
            "op": 2,
            "table": table,
            "columns": cols,
            "values": [values],  # envolvemos en lista para uniformidad
        }

    # Parsear cada objeto { ... }
    values = []
    for obj in objects:
        parts = _split_csv_top(obj)
        parsed_row = [_parse_literal(p) for p in parts]
        values.append(parsed_row)

    return {
        "op": 2,
        "table": table,
        "columns": cols,
        "values": values,  # lista de listas (una por objeto)
    }

def parse_import(sql: str) -> Dict[str, Any]:
    m = re.match(
        r'^\s*IMPORT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\s+FROM\s+FILE\s+["\'](.+?)["\'](?:\s+USING\s+INDEX\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\))?\s*$',
        sql, flags=re.IGNORECASE | re.DOTALL
    )
    if not m:
        raise ValueError("IMPORT inválido")

    table, filepath, idx_type, idx_col = m.group(1), m.group(2), m.group(3), m.group(4)
    out: Dict[str, Any] = {
        "op": 3,
        "table": table,
        "file": filepath,
    }
    if idx_type and idx_col:
        out["index"] = {"type": idx_type, "column": idx_col}
    return out

def parse_delete(sql: str) -> Dict[str, Any]:
    m = re.match(
        r"^\s*DELETE\s+FROM\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:WHERE\s+(.+))?$",
        sql, flags=re.IGNORECASE | re.DOTALL
    )
    if not m:
        raise ValueError("DELETE inválido")

    table = m.group(1)
    cond = (m.group(2) or "").strip()

    out: Dict[str, Any] = {"op": 4, "table": table}
    if not cond:
        return out

    m_eq = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", cond, flags=re.IGNORECASE)
    if m_eq:
        field = m_eq.group(1)
        value = _parse_literal(m_eq.group(2))
        out["where"] = {"type": "eq", "field": field, "value": value}
        return out

    out["where"] = {"type": "raw", "expr": cond}
    return out

@router.post("/", response_class=JSONResponse)
async def parse_sql_endpoint(query: Query):
    sql = query.text.strip().rstrip(";")
    if not sql:
        return JSONResponse(status_code=400, content="Consulta vacía.")

    try:
        head = sql.split(None, 1)[0].lower()

        if head == "create":
            result = parse_create(sql)
        elif head == "select":
            result = parse_select(sql)
        elif head == "insert":
            result = parse_insert(sql)
        elif head == "import":
            result = parse_import(sql)
        elif head == "delete":
            result = parse_delete(sql)
        else:
            result = {"op": -1, "raw": sql}

        return JSONResponse(status_code=200, content=result)

    except ValueError as e:
        return JSONResponse(status_code=400, content=str(e))

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=str(e)
        )
