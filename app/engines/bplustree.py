import struct
import os
from typing import Callable, Any, Optional

R = 40  # Hijos por nodo índice
M = 20  # Registros por página datos


class Node:
    # El formato (FMT) depende de KEY_LEN. Lo seteamos en tiempo de ejecución.
    FMT: str = ""
    SIZE: int = 0

    def __init__(self, is_leaf: bool = True, count: int = 0):
        self.is_leaf = is_leaf
        self.count = count
        self.keys = []       # lista de str (claves separadoras)
        self.children = []   # lista de ints (punteros a hijo o página)


class DataPage:
    # El tamaño total depende del RECORD_SIZE del record. Lo seteamos en tiempo de ejecución.
    HEADER_FMT = "ii"
    HEADER_SIZE = struct.calcsize(HEADER_FMT)
    SIZE: int = 0           # se asigna en runtime: HEADER_SIZE + M * record_size

    def __init__(self, count: int = 0, next_page: int = -1):
        self.count = count
        self.next_page = next_page
        self.records = []    # lista de records (objetos)


class BPlusTreeFile:
    """
    Uso:
      # Para Song (clave 'track_id'):
      tree = BPlusTreeFile("songs.dat", "songs.idx", record_cls=Song, key_attr="track_id", key_len=30)

      # Para Restaurantes (clave 'id' int -> se convierte a str para ordenar):
      tree = BPlusTreeFile("rest.dat", "rest.idx", record_cls=Restaurantes, key_attr="id", key_len=30)
    """
    def __init__(
        self,
        datafile: str,
        indexfile: str,
        record_cls: Any,
        key_attr: Optional[str] = "track_id",
        key_len: int = 30,
        key_to_str: Optional[Callable[[Any], str]] = None,
    ):
        self.datafile = datafile
        self.indexfile = indexfile

        # === Dependencias de record (antes estaba fijo a Song) ===
        self.Record = record_cls
        self.record_size = int(getattr(record_cls, "RECORD_SIZE"))
        # Cómo obtengo la clave desde un record:
        if key_attr is not None:
            self._key_get = lambda obj: getattr(obj, key_attr)
        else:
            # Si te pasaron una función por fuera, úsala; si no, intenta 'track_id'
            self._key_get = lambda obj: getattr(obj, "track_id")

        # Conversión a string (para almacenar/ordenar en nodos):
        self._key_to_str = key_to_str or (lambda v: str(v))

        # === Ajustes de formatos dependientes de key_len y record_size ===
        self.KEY_LEN = int(key_len)
        Node.FMT  = "?i" + (f"{self.KEY_LEN}s" * (R - 1)) + ("i" * R)
        Node.SIZE = struct.calcsize(Node.FMT)
        DataPage.SIZE = DataPage.HEADER_SIZE + M * self.record_size

        self._init_files()

    # ========== API Pública ==========

    def search(self, key: Any):
        """Busca una clave específica"""
        key_s = self._key_to_str(key)
        page_idx = self._find_leaf_page(key_s, 0)
        page = self._read_page(page_idx)

        for r in page.records[:page.count]:
            if self._key_to_str(self._key_get(r)) == key_s:
                return r
        return None

    def rangeSearch(self, begin: Any, end: Any):
        """Busca todas las claves en el rango [begin, end] (inclusive)"""
        begin_s = self._key_to_str(begin)
        end_s   = self._key_to_str(end)

        page_idx = self._find_leaf_page(begin_s, 0)
        results = []

        while page_idx >= 0:
            page = self._read_page(page_idx)
            for r in page.records[:page.count]:
                k = self._key_to_str(self._key_get(r))
                if begin_s <= k <= end_s:
                    results.append(r)
                elif k > end_s:
                    return results
            page_idx = page.next_page

        return results

    def add(self, record):
        """Inserta o actualiza un registro (según su clave)"""
        key_s = self._key_to_str(self._key_get(record))
        if not key_s:
            return

        # Encontrar página destino
        node_path = []
        page_idx = self._find_leaf_page(key_s, 0, node_path)

        # Insertar en página
        page = self._read_page(page_idx)
        self._insert_in_page(page, record)

        # Verificar overflow
        if page.count > M:
            self._write_page(page, page_idx)
            new_page_idx, sep_key = self._split_page(page_idx)
            self._insert_in_index(node_path, sep_key, new_page_idx)
        else:
            self._write_page(page, page_idx)

    def remove(self, key: Any):
        key_s = self._key_to_str(key)
        page_idx = self._find_leaf_page(key_s, 0)
        page = self._read_page(page_idx)

        # Buscar y eliminar
        found = False
        new_records = []
        for r in page.records[:page.count]:
            if self._key_to_str(self._key_get(r)) != key_s or found:
                new_records.append(r)
            else:
                found = True

        if not found:
            return False

        page.records = new_records
        page.count = len(new_records)
        self._write_page(page, page_idx)
        return True

    # ========== Inicialización de archivos ==========

    def _init_files(self):
        if not os.path.exists(self.indexfile):
            root = Node(is_leaf=True, count=0)
            root.children = [0]
            self._write_node(root, 0)
        if not os.path.exists(self.datafile):
            self._write_page(DataPage(), 0)

    # ========== Métodos Internos ==========

    def _find_leaf_page(self, key_s: str, node_pos: int, path=None):
        """Encuentra la página hoja que debería contener la clave (string)"""
        node = self._read_node(node_pos)

        # Encontrar posición correcta
        pos = 0
        for i in range(node.count):
            if key_s >= node.keys[i]:
                pos = i + 1
            else:
                break

        # Asegurar que pos esté en rango válido
        pos = min(pos, len(node.children) - 1) if node.children else 0

        if path is not None:
            path.append((node_pos, pos))

        if node.is_leaf:
            # Retornar el hijo en la posición calculada
            if pos < len(node.children) and node.children[pos] >= 0:
                return node.children[pos]
            # Fallback: primer hijo válido
            for child in node.children:
                if child >= 0:
                    return child
            return 0
        else:
            # Continuar descenso
            if pos < len(node.children) and node.children[pos] >= 0:
                return self._find_leaf_page(key_s, node.children[pos], path)
            # Fallback: primer hijo válido
            for child in node.children:
                if child >= 0:
                    return self._find_leaf_page(key_s, child, path)
            return 0

    def _insert_in_page(self, page: DataPage, record):
        """Inserta ordenado en página de datos"""
        key_new = self._key_to_str(self._key_get(record))

        # Buscar posición
        pos = 0
        for i in range(page.count):
            key_i = self._key_to_str(self._key_get(page.records[i]))
            if key_i == key_new:
                # Actualizar existente
                page.records[i] = record
                return
            if key_i < key_new:
                pos = i + 1

        # Insertar nuevo
        page.records.insert(pos, record)
        page.count += 1

    def _split_page(self, page_idx: int):
        """Divide una página llena en dos"""
        left = self._read_page(page_idx)
        mid = (left.count + 1) // 2  # División equilibrada

        # Alocar página derecha PRIMERO
        right_idx = self._alloc_page()

        # Crear página derecha con la segunda mitad
        right = DataPage(count=left.count - mid, next_page=left.next_page)
        right.records = left.records[mid:left.count]

        # Actualizar izquierda con la primera mitad
        left.records = left.records[:mid]
        left.count = mid
        left.next_page = right_idx

        # Escribir ambas páginas
        self._write_page(left, page_idx)
        self._write_page(right, right_idx)

        # Clave separadora: primera clave del lado derecho
        sep_key = self._key_to_str(self._key_get(right.records[0]))
        return right_idx, sep_key

    def _insert_in_index(self, path, key_s: str, page_idx: int):
        """Inserta clave en el índice, manejando splits si es necesario"""
        if not path:
            # Crear nueva raíz
            old_root = self._read_node(0)
            new_root_idx = self._alloc_node()
            self._write_node(old_root, new_root_idx)

            new_root = Node(is_leaf=False, count=1)
            new_root.keys = [key_s]
            new_root.children = [new_root_idx, page_idx]
            self._write_node(new_root, 0)
            return

        node_pos, child_pos = path.pop()
        node = self._read_node(node_pos)

        # Insertar clave y puntero
        insert_pos = 0
        for i in range(node.count):
            if key_s >= node.keys[i]:
                insert_pos = i + 1
            else:
                break

        node.keys.insert(insert_pos, key_s)
        node.children.insert(child_pos + 1, page_idx)
        node.count += 1

        # Verificar overflow
        if node.count <= R - 1:
            self._write_node(node, node_pos)
        else:
            new_node_idx, up_key = self._split_node(node, node_pos)
            self._insert_in_index(path, up_key, new_node_idx)

    def _split_node(self, node: Node, node_pos: int):
        """Divide un nodo índice lleno"""
        mid = node.count // 2

        # Nodo derecho
        right = Node(is_leaf=node.is_leaf, count=node.count - mid - 1)
        right.keys = node.keys[mid + 1:]
        right.children = node.children[mid + 1:]

        # Actualizar nodo izquierdo
        up_key = node.keys[mid]
        node.keys = node.keys[:mid]
        node.children = node.children[:mid + 1]
        node.count = mid

        # Escribir
        right_idx = self._alloc_node()
        self._write_node(node, node_pos)
        self._write_node(right, right_idx)

        return right_idx, up_key

    # ========== I/O ==========

    def _read_node(self, pos: int):
        with open(self.indexfile, "rb") as f:
            f.seek(pos * Node.SIZE)
            data = f.read(Node.SIZE)

        if len(data) < Node.SIZE:
            return Node()

        unpacked = struct.unpack(Node.FMT, data)
        is_leaf = bool(unpacked[0])
        count = int(unpacked[1])

        node = Node(is_leaf, count)
        node.keys = []
        # claves como strings (decodificadas y strip de nulls/espacios)
        for i in range(count):
            raw = unpacked[2 + i]
            key = raw.decode(errors="ignore").rstrip('\x00').strip()
            if key:
                node.keys.append(key)

        node.children = list(unpacked[2 + (R - 1):2 + (R - 1) + R])[:count + 1]
        return node

    def _write_node(self, node: Node, pos: int):
        # Empaquetar claves a KEY_LEN bytes
        keys = [b'\x00' * self.KEY_LEN] * (R - 1)
        for i in range(min(node.count, R - 1)):
            kb = (node.keys[i] or "").encode()[:self.KEY_LEN]
            keys[i] = kb + b'\x00' * (self.KEY_LEN - len(kb))

        children = (node.children + [-1] * R)[:R]
        packed = struct.pack(Node.FMT, node.is_leaf, node.count, *keys, *children)

        with open(self.indexfile, "r+b" if os.path.exists(self.indexfile) else "wb") as f:
            f.seek(pos * Node.SIZE)
            f.write(packed)

    def _alloc_node(self):
        size = os.path.getsize(self.indexfile) if os.path.exists(self.indexfile) else 0
        return size // Node.SIZE

    def _read_page(self, pos: int):
        with open(self.datafile, "rb") as f:
            f.seek(pos * DataPage.SIZE)
            header = f.read(DataPage.HEADER_SIZE)

            if len(header) < DataPage.HEADER_SIZE:
                return DataPage()

            count, next_page = struct.unpack(DataPage.HEADER_FMT, header)
            raw = f.read(M * self.record_size)

        page = DataPage(count, next_page)
        for i in range(min(count, M)):
            start = i * self.record_size
            end = start + self.record_size
            chunk = raw[start:end]

            if len(chunk) == self.record_size:
                try:
                    rec = self.Record.unpack(chunk)
                    if rec:
                        page.records.append(rec)
                except Exception:
                    # Skip registros corruptos
                    continue

        page.count = len(page.records)
        return page

    def _write_page(self, page: DataPage, pos: int):
        page.count = min(page.count, M, len(page.records))
        header = struct.pack(DataPage.HEADER_FMT, page.count, page.next_page)

        body = bytearray(M * self.record_size)
        for i in range(page.count):
            chunk = page.records[i].pack()
            body[i * self.record_size:(i + 1) * self.record_size] = chunk

        with open(self.datafile, "r+b" if os.path.exists(self.datafile) else "wb") as f:
            f.seek(pos * DataPage.SIZE)
            f.write(header)
            f.write(body)

    def _alloc_page(self):
        size = os.path.getsize(self.datafile) if os.path.exists(self.datafile) else 0
        pos = size // DataPage.SIZE
        self._write_page(DataPage(), pos)
        return pos
