import os
from pathlib import Path

if os.path.exists("app/data"):
    DATA_ROOT = Path("app/data").resolve()
else:
    DATA_ROOT = Path(os.getenv("DATA_DIR", "/app/data")).resolve()

TABLES_ROOT = DATA_ROOT / "tables"

BPLUSTREE_DIR = TABLES_ROOT / "bplustree"
ISAM_DIR      = TABLES_ROOT / "isam"
RTREE_DIR     = TABLES_ROOT / "rtree"
EXTHASH_DIR   = TABLES_ROOT / "exthashing"
SEQFILE_DIR = TABLES_ROOT / "seqfile"

for p in (BPLUSTREE_DIR, ISAM_DIR, RTREE_DIR, EXTHASH_DIR, SEQFILE_DIR):
    p.mkdir(parents=True, exist_ok=True)
