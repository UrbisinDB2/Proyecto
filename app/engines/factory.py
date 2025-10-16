from typing import Any
from app.settings import BPLUSTREE_DIR

def build_bplustree(table: str, spec: dict):
    from app.engines.bplustree import BPlusTreeFile

    datafile  = (BPLUSTREE_DIR / f"{table.lower()}.dat").as_posix()
    indexfile = (BPLUSTREE_DIR / f"{table.lower()}.idx").as_posix()

    return BPlusTreeFile(
        datafile=datafile,
        indexfile=indexfile
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
