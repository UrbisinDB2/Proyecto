import importlib
from pathlib import Path
from typing import Any, Callable, Optional
from app.settings import BPLUSTREE_DIR

def import_record_class(table_name: str):
    mod = importlib.import_module(f"data.records.{table_name.lower()}")
    return getattr(mod, table_name[:1].upper() + table_name[1:])

def build_bplustree(table: str, record_cls: Any, spec: dict):
    from app.engines.bplustree import BPlusTreeFile
    key_attr = spec.get("key_attr", "track_id")
    key_len  = int(spec.get("key_len", 30))
    key_to_str: Optional[Callable] = spec.get("key_to_str")

    datafile  = (BPLUSTREE_DIR / f"{table.lower()}.dat").as_posix()
    indexfile = (BPLUSTREE_DIR / f"{table.lower()}.idx").as_posix()

    return BPlusTreeFile(
        datafile=datafile,
        indexfile=indexfile,
        record_cls=record_cls,
        key_attr=key_attr,
        key_len=key_len,
        key_to_str=key_to_str,
    )

# Stubs para otros motores (cuando los tengas, impleméntalos aquí):
def build_isam(table: str, record_cls: Any, spec: dict):
    raise NotImplementedError("ISAM no implementado aún")

def build_rtree(table: str, record_cls: Any, spec: dict):
    raise NotImplementedError("RTree no implementado aún")

def build_exthashing(table: str, record_cls: Any, spec: dict):
    raise NotImplementedError("ExtHashing no implementado aún")

def build_seqfile(table: str, record_cls: Any, spec: dict):
    raise NotImplementedError("SeqFile no implementado aún")

ENGINE_BUILDERS = {
    "bplustree": build_bplustree,
    "isam": build_isam,
    "rtree": build_rtree,
    "exthashing": build_exthashing,
    "seqfile": build_seqfile
}
