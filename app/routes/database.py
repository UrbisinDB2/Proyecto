from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pathlib import Path
import re
import csv, inspect

from app.models.parsed_query import ParsedQuery
from app.engines.factory import ENGINE_BUILDERS
from app.settings import DATA_ROOT, BPLUSTREE_DIR
from app.data.records.song import Song

router = APIRouter()


def generate_record(schema: dict) -> str:
    table = schema["table"]
    cols = schema["columns"]
    class_name = table[:1].upper() + table[1:]

    def py_hint(ctype: str) -> str:
        ct = ctype.lower()
        if ct == "int": return "int"
        if ct == "float": return "float"
        if ct == "date": return "str"
        if ct.startswith("varchar("): return "str"
        if ct == "array(float)": return "list[float]"
        return "object"

    def fmt_token(ctype: str):
        ct = ctype.lower()
        if ct == "int": return "i"
        if ct == "float": return "f"
        if ct == "date": return "12s"
        if ct.startswith("varchar("):
            n = int(re.search(r"varchar\((\d+)\)", ct).group(1))
            return f"{n}s"
        if ct == "array(float)": return ["f", "f"]
        raise ValueError(f"Tipo no soportado: {ctype}")

    fmt_parts = []
    init_names: list[str] = []
    init_types: list[str] = []
    prepack_lines = []
    pack_args_code = []
    unpack_tuple_vars = []
    post_unpack_lines = []
    ctor_kwargs = []

    for c in cols:
        name = c["name"]
        ctype = c["type"]

        init_names.append(name)
        init_types.append(py_hint(ctype))

        token = fmt_token(ctype)
        if isinstance(token, list):
            fmt_parts.extend(token)
        else:
            fmt_parts.append(token)

        ct = ctype.lower()
        if ct.startswith("varchar("):
            n = int(re.search(r"varchar\((\d+)\)", ct).group(1))
            prepack_lines.append(
                f"{name}_bytes = (self.{name} or '').encode('utf-8')[:{n}].ljust({n}, b'\\x00')"
            )
            pack_args_code.append(f"{name}_bytes")
            tup_var = f"_{name}_raw"
            unpack_tuple_vars.append(tup_var)
            post_unpack_lines.append(
                f"{name} = {tup_var}.decode('utf-8', errors='ignore').rstrip('\\x00').strip()"
            )
            ctor_kwargs.append(f"{name}={name}")

        elif ct == "date":
            prepack_lines.append(
                f"{name}_bytes = (self.{name} or '').encode('utf-8')[:12].ljust(12, b'\\x00')"
            )
            pack_args_code.append(f"{name}_bytes")
            tup_var = f"_{name}_raw"
            unpack_tuple_vars.append(tup_var)
            post_unpack_lines.append(
                f"{name} = {tup_var}.decode('utf-8', errors='ignore').rstrip('\\x00').strip()"
            )
            ctor_kwargs.append(f"{name}={name}")

        elif ct == "int":
            pack_args_code.append(f"self.{name}")
            tup_var = f"_{name}"
            unpack_tuple_vars.append(tup_var)
            post_unpack_lines.append(f"{name} = {tup_var}")
            ctor_kwargs.append(f"{name}={name}")

        elif ct == "float":
            pack_args_code.append(f"float(self.{name})")
            tup_var = f"_{name}"
            unpack_tuple_vars.append(tup_var)
            post_unpack_lines.append(f"{name} = {tup_var}")
            ctor_kwargs.append(f"{name}={name}")

        elif ct == "array(float)":
            prepack_lines.append(
                f"{name}_vals = (self.{name} or [0.0, 0.0])\n"
                f"        assert len({name}_vals) == 2, 'El array {name} debe tener longitud 2'"
            )
            pack_args_code.append(f"float({name}_vals[0])")
            pack_args_code.append(f"float({name}_vals[1])")
            v1, v2 = f"_{name}_0", f"_{name}_1"
            unpack_tuple_vars.extend([v1, v2])
            post_unpack_lines.append(f"{name} = [{v1}, {v2}]")
            ctor_kwargs.append(f"{name}={name}")

    fmt_str = '"' + "".join(fmt_parts) + '"'
    init_sig = ", ".join([f"{n}: {t}" for n, t in zip(init_names, init_types)])
    tuple_vars_str = ", ".join(unpack_tuple_vars)
    ctor_kwargs_str = ",\n                ".join(ctor_kwargs)

    source = (
            "import struct\n\n\n"
            f"class {class_name}:\n"
            f"    FMT = {fmt_str}\n"
            f"    RECORD_SIZE = struct.calcsize(FMT)\n\n"
            f"    def __init__(self, {init_sig}):\n" +
            "".join([f"        self.{n} = {n}\n" for n in init_names]) + "\n" +
            "    def pack(self):\n" +
            "".join([f"        {line}\n" for line in prepack_lines]) +
            "        record = struct.pack(\n"
            "            self.FMT,\n" +
            "".join([f"            {arg},\n" for arg in pack_args_code]) +
            "        )\n"
            "        return record\n\n"
            "    @staticmethod\n"
            "    def unpack(data):\n"
            f"        if not data or len(data) < {class_name}.RECORD_SIZE:\n"
            "            return None\n\n"
            "        try:\n"
            f"            unpacked = struct.unpack({class_name}.FMT, data)\n"
            f"            {tuple_vars_str} = unpacked\n" +
            "".join([f"            {line}\n" for line in post_unpack_lines]) +
            "\n"
            f"            return {class_name}(\n"
            f"                {ctor_kwargs_str}\n"
            "            )\n"
            "        except Exception:\n"
            "            return None\n\n"
            "    def __repr__(self):\n"
            f"        return f\"{class_name}(" +
            ", ".join([f"{n}={{self.{n}!r}}" for n in init_names[:3]]) +
            "... )\"\n"
    )
    return source


def _csv_path_for_song(q_file: str | None) -> Path:
    datasets = DATA_ROOT / "datasets"
    if q_file:
        p = Path(q_file)
        if not p.is_absolute():
            p = datasets / p
        return p
    return datasets / "spotify_songs.csv"


def _import_songs_from_csv(csv_path: Path, index: str) -> dict:
    table = "song"
    spec = {"type": index, "key_attr": "track_id", "key_len": 30}
    engine = ENGINE_BUILDERS[index](table, spec)

    record_cls = Song
    params = [p.name for p in inspect.signature(record_cls.__init__).parameters.values() if p.name != "self"]
    pset = {p.lower(): p for p in params}

    inserted = skipped = 0
    int_fields = {"track_popularity", "duration_ms"}
    float_fields = {"acousticness", "instrumentalness"}

    with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                kwargs = {}
                for k, v in row.items():
                    if not k:
                        continue
                    key = pset.get(k.strip().lower())
                    if key is None:
                        continue
                    val = (v or "").strip()
                    kwargs[key] = val

                for fn in int_fields:
                    if fn in kwargs and kwargs[fn] not in (None, ""):
                        try:
                            kwargs[fn] = int(float(kwargs[fn]))
                        except Exception:
                            pass
                for fn in float_fields:
                    if fn in kwargs and kwargs[fn] not in (None, ""):
                        try:
                            kwargs[fn] = float(kwargs[fn])
                        except Exception:
                            pass

                if not kwargs.get("track_id"):
                    raise ValueError("fila sin track_id")

                rec = record_cls(**kwargs)
                engine.add(rec)
                inserted += 1
            except Exception:
                skipped += 1

    return {
        "table": table,
        "engine": index,
        "inserted": inserted,
        "skipped": skipped,
        "datafile": (BPLUSTREE_DIR / "song.dat").as_posix(),
        "indexfile": (BPLUSTREE_DIR / "song.idx").as_posix(),
    }


def _get_engine_for_table(table: str, engine_type: str = "bplustree"):
    spec = {"type": engine_type, "key_attr": "track_id", "key_len": 30}
    return ENGINE_BUILDERS[engine_type](table, spec)


def _song_to_dict(song: Song) -> dict:
    return {
        "track_id": song.track_id,
        "track_name": song.track_name,
        "track_artist": song.track_artist,
        "track_popularity": song.track_popularity,
        "track_album_id": song.track_album_id,
        "track_album_name": song.track_album_name,
        "track_album_release_date": song.track_album_release_date,
        "acousticness": song.acousticness,
        "instrumentalness": song.instrumentalness,
        "duration_ms": song.duration_ms
    }


def _return_all_songs(table: str = "song", engine_type: str = "bplustree") -> list[dict]:
    engine = _get_engine_for_table(table, engine_type)
    results = []

    if hasattr(engine, '_read_page'):
        page_idx = 0
        visited = set()
        while page_idx >= 0 and page_idx not in visited:
            visited.add(page_idx)
            page = engine._read_page(page_idx)
            for song in page.records[:page.count]:
                results.append(_song_to_dict(song))
            page_idx = page.next_page
    elif hasattr(engine, 'scan'):
        results = [_song_to_dict(s) for s in engine.scan()]
    elif hasattr(engine, 'getAll'):
        results = [_song_to_dict(s) for s in engine.getAll()]

    return results


def _return_song(key: str, table: str = "song", engine_type: str = "bplustree") -> dict | None:
    engine = _get_engine_for_table(table, engine_type)
    song = engine.search(key)
    return _song_to_dict(song) if song else None


def _return_range_search(begin: str, end: str, table: str = "song", engine_type: str = "bplustree") -> list[dict]:
    engine = _get_engine_for_table(table, engine_type)

    if hasattr(engine, 'rangeSearch'):
        songs = engine.rangeSearch(begin, end)
        return [_song_to_dict(s) for s in songs]
    else:
        all_songs = _return_all_songs(table, engine_type)
        return [s for s in all_songs if begin <= s["track_id"] <= end]


def _insert_song(values: list, table: str = "song", engine_type: str = "bplustree") -> bool:
    engine = _get_engine_for_table(table, engine_type)
    song = Song(*values)
    engine.add(song)
    return True


def _delete_song(key: str, table: str = "song", engine_type: str = "bplustree") -> bool:
    engine = _get_engine_for_table(table, engine_type)
    return engine.remove(key)


@router.post("/", response_class=JSONResponse)
async def run_query(query: ParsedQuery):
    op = query.op
    q = dict(query)

    if op == 0:  # CREATE TABLE
        schema = dict(query)
        record = generate_record(schema)
        filename = str(schema["table"]).lower() + ".py"
        base_dir = Path(__file__).resolve().parents[2]
        out_dir = base_dir / "data" / "records"
        out_path = out_dir / filename
        out_path.write_text(record, encoding="utf-8")

        return JSONResponse(status_code=200, content={"message": f'Created record: {schema["table"]}'})

    elif op == 1:  # SELECT
        table = query.table or "song"
        engine_type = "bplustree"

        if q.get("where"):
            if q["where"]["type"] == "eq":
                key = str(q["where"]["value"])
                song = _return_song(key, table, engine_type)

                if song:
                    return JSONResponse(status_code=200, content={
                        "result": [song],
                        "count": 1,
                        "engine": engine_type
                    })
                else:
                    return JSONResponse(status_code=404, content={
                        "message": "Record not found",
                        "result": [],
                        "count": 0,
                        "engine": engine_type
                    })

            elif q["where"]["type"] == "between":
                begin = str(q["where"]["from"])
                end = str(q["where"]["to"])
                songs = _return_range_search(begin, end, table, engine_type)

                return JSONResponse(status_code=200, content={
                    "result": songs,
                    "count": len(songs),
                    "engine": engine_type
                })
        else:
            songs = _return_all_songs(table, engine_type)
            return JSONResponse(status_code=200, content={
                "result": songs,
                "count": len(songs),
                "engine": engine_type
            })

    elif op == 2:  # INSERT
        table = query.table or "song"
        engine_type = "bplustree"
        values = q.get("values", [])

        inserted = 0
        for row in values:
            if _insert_song(row, table, engine_type):
                inserted += 1

        return JSONResponse(status_code=200, content={
            "message": f"Inserted {inserted} record(s)",
            "inserted": inserted,
            "total": len(values),
            "engine": engine_type
        })

    elif op == 3:  # IMPORT
        index = q.get("index", {})
        csv_path = _csv_path_for_song(q.get("file"))
        stats = _import_songs_from_csv(csv_path, str(index.get("type", "bplustree")))

        return JSONResponse(status_code=200, content=stats)

    elif op == 4:  # DELETE
        table = query.table or "song"
        engine_type = "bplustree"
        where_dict = q.get("where", {})

        if where_dict.get("type") != "eq":
            return JSONResponse(status_code=400, content={
                "message": "DELETE only supports WHERE with exact match"
            })

        key = str(where_dict["value"])
        success = _delete_song(key, table, engine_type)
        status = 200 if success else 404

        return JSONResponse(status_code=status, content={
            "message": f"Record '{key}' {'deleted' if success else 'not found'}",
            "deleted": success,
            "engine": engine_type
        })

    else:
        return JSONResponse(status_code=400, content={
            "message": f"Unknown operation: {op}"
        })