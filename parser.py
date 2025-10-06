import re

def normalize_type(raw_type: str) -> str:
    raw_type = raw_type.strip().lower()

    # varchar[n]
    if raw_type.startswith("varchar["):
        length = re.search(r"\[(\d+)\]", raw_type)
        if length:
            return f"varchar({length.group(1)})"
        return "varchar"

    # array[tipo]
    if raw_type.startswith("array["):
        subtype = re.search(r"\[([a-z0-9_]+)\]", raw_type)
        if subtype:
            return f"array({subtype.group(1)})"
        return "array"

    # tipos simples
    if raw_type in ("int", "float", "date", "string"):
        return raw_type

    # fallback
    return raw_type

def parse_sql_query(text: str):
    parsed_query = {}
    t = text.lower()
    t = t.split(" ")

    if t[0] == "create":
        parsed_query["op"] = 0

        pattern = r"^\s*CREATE\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*$"
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if match:
            table_name = match.group(1)
            columns_part = match.group(2)
        else:
            print("No se pudo parsear.")

        parsed_query["table_name"] = table_name
        parsed_query["columns"] = []

        columns = columns_part.split(",")

        for column in columns:
            c = {}
            column = column.split(" ")
            c["name"] = column[0]
            c["type"] = normalize_type(column[1])
            parsed_query["columns"].append(c)

    elif t[0] == "select":
        parsed_query["op"] = 1
        parsed_query["columns"] = t[1]
        parsed_query["table"] = t[3]




    elif t[0] == "insert":
        parsed_query["op"] = 2
    elif t[0] == "import":
        parsed_query["op"] = 3
    elif t[0] == "delete":
        parsed_query["op"] = 4

    print(parsed_query)

    return parsed_query

parse_sql_query(r'select * from Restaurantes where id = x')
