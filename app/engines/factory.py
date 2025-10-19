from typing import Any
from app.settings import BPLUSTREE_DIR, EXTHASH_DIR

def build_bplustree(table: str):
    from app.engines.bplustree import BPlusTreeFile

    datafile  = (BPLUSTREE_DIR / f"{table.lower()}.dat").as_posix()
    indexfile = (BPLUSTREE_DIR / f"{table.lower()}.idx").as_posix()

    return BPlusTreeFile(
        datafile=datafile,
        indexfile=indexfile
    )

# Stubs para otros motores (cuando los tengas, impleméntalos aquí):
def build_isam(table: str):
    raise NotImplementedError("ISAM no implementado aún")

def build_rtree(table: str):
    raise NotImplementedError("RTree no implementado aún")

def build_exthashing(table: str):
    from app.engines.extendiblehashing import ExtendibleHashingFile

    datafile = (EXTHASH_DIR / f"{table.lower()}.dat").as_posix()
    dirfile = (EXTHASH_DIR / f"{table.lower()}.dir").as_posix()

    return ExtendibleHashingFile(
        datafile=datafile,
        dirfile=dirfile
    )

def build_seqfile(table: str):
    raise NotImplementedError("SeqFile no implementado aún")

ENGINE_BUILDERS = {
    "bplustree": build_bplustree,
    "isam": build_isam,
    "rtree": build_rtree,
    "exthashing": build_exthashing,
    "seqfile": build_seqfile
}
