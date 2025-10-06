import struct
import os
from app.models.song import Song

R = 40  # Hijos por nodo índice
M = 20  # Registros por página datos
KEY_LEN = 30


class Node:
    FMT = "?i" + ("30s" * (R - 1)) + ("i" * R)
    SIZE = struct.calcsize(FMT)

    def __init__(self, is_leaf=True, count=0):
        self.is_leaf = is_leaf
        self.count = count
        self.keys = []
        self.children = []


class DataPage:
    HEADER_FMT = "ii"
    HEADER_SIZE = struct.calcsize(HEADER_FMT)
    SIZE = HEADER_SIZE + M * Song.RECORD_SIZE

    def __init__(self, count=0, next_page=-1):
        self.count = count
        self.next_page = next_page
        self.records = []


class BPlusTreeFile:
    def __init__(self, datafile: str, indexfile: str):
        self.datafile = datafile
        self.indexfile = indexfile
        self._init_files()

    def _init_files(self):
        if not os.path.exists(self.indexfile):
            root = Node(is_leaf=True, count=0)
            root.children = [0]
            self._write_node(root, 0)
        if not os.path.exists(self.datafile):
            self._write_page(DataPage(), 0)

    # ========== API Pública ==========

    def search(self, key: str):
        """Busca una clave específica"""
        page_idx = self._find_leaf_page(key, 0)
        page = self._read_page(page_idx)

        for r in page.records[:page.count]:
            if r.track_id == key:
                return r
        return None

    def rangeSearch(self, begin: str, end: str):
        """Busca todas las claves en el rango [begin, end]"""
        page_idx = self._find_leaf_page(begin, 0)
        results = []

        while page_idx >= 0:
            page = self._read_page(page_idx)
            for r in page.records[:page.count]:
                if begin <= r.track_id <= end:
                    results.append(r)
                elif r.track_id > end:
                    return results
            page_idx = page.next_page

        return results

    def add(self, song: Song):
        """Inserta o actualiza una canción"""
        if not song.track_id:
            return

        # Encontrar página destino
        node_path = []
        page_idx = self._find_leaf_page(song.track_id, 0, node_path)

        # Insertar en página
        page = self._read_page(page_idx)
        self._insert_in_page(page, song)

        # Verificar overflow
        if page.count > M:
            self._write_page(page, page_idx)
            new_page_idx, sep_key = self._split_page(page_idx)
            self._insert_in_index(node_path, sep_key, new_page_idx)
        else:
            self._write_page(page, page_idx)

    def remove(self, key: str):
        """Elimina una clave (lazy deletion)"""
        page_idx = self._find_leaf_page(key, 0)
        page = self._read_page(page_idx)

        # Buscar y eliminar
        found = False
        new_records = []
        for r in page.records[:page.count]:
            if r.track_id != key or found:
                new_records.append(r)
            else:
                found = True

        if not found:
            return False

        page.records = new_records
        page.count = len(new_records)
        self._write_page(page, page_idx)
        return True

    # ========== Métodos Internos ==========

    def _find_leaf_page(self, key: str, node_pos: int, path=None):
        """Encuentra la página hoja que debería contener la clave"""
        node = self._read_node(node_pos)

        # Encontrar posición correcta
        pos = 0
        for i in range(node.count):
            if key >= node.keys[i]:
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
                return self._find_leaf_page(key, node.children[pos], path)
            # Fallback: primer hijo válido
            for child in node.children:
                if child >= 0:
                    return self._find_leaf_page(key, child, path)
            return 0

    def _insert_in_page(self, page: DataPage, song: Song):
        """Inserta ordenado en página de datos"""
        # Buscar posición
        pos = 0
        for i in range(page.count):
            if page.records[i].track_id == song.track_id:
                # Actualizar existente
                page.records[i] = song
                return
            if page.records[i].track_id < song.track_id:
                pos = i + 1

        # Insertar nuevo
        page.records.insert(pos, song)
        page.count += 1

    def _split_page(self, page_idx: int):
        """Divide una página llena en dos"""
        left = self._read_page(page_idx)
        mid = (left.count + 1) // 2  # División más equilibrada

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

        return right_idx, right.records[0].track_id

    def _insert_in_index(self, path, key: str, page_idx: int):
        """Inserta clave en el índice, manejando splits si es necesario"""
        if not path:
            # Crear nueva raíz
            old_root = self._read_node(0)
            new_root_idx = self._alloc_node()
            self._write_node(old_root, new_root_idx)

            new_root = Node(is_leaf=False, count=1)
            new_root.keys = [key]
            new_root.children = [new_root_idx, page_idx]
            self._write_node(new_root, 0)
            return

        node_pos, child_pos = path.pop()
        node = self._read_node(node_pos)

        # Insertar clave y puntero
        insert_pos = 0
        for i in range(node.count):
            if key >= node.keys[i]:
                insert_pos = i + 1
            else:
                break

        node.keys.insert(insert_pos, key)
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
        for i in range(count):
            key = unpacked[2 + i].decode().rstrip('\x00').strip()
            if key:
                node.keys.append(key)

        node.children = list(unpacked[2 + R - 1:2 + R - 1 + R])[:count + 1]
        return node

    def _write_node(self, node: Node, pos: int):
        keys = [b'\x00' * KEY_LEN] * (R - 1)
        for i in range(min(node.count, R - 1)):
            k = node.keys[i].encode()[:KEY_LEN]
            keys[i] = k + b'\x00' * (KEY_LEN - len(k))

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
            raw = f.read(M * Song.RECORD_SIZE)

        page = DataPage(count, next_page)
        for i in range(min(count, M)):
            start = i * Song.RECORD_SIZE
            end = start + Song.RECORD_SIZE
            chunk = raw[start:end]

            if len(chunk) == Song.RECORD_SIZE:
                try:
                    song = Song.unpack(chunk)
                    if song:
                        page.records.append(song)
                except Exception as e:
                    # Skip registros corruptos
                    continue

        page.count = len(page.records)
        return page

    def _write_page(self, page: DataPage, pos: int):
        page.count = min(page.count, M, len(page.records))
        header = struct.pack(DataPage.HEADER_FMT, page.count, page.next_page)

        body = bytearray(M * Song.RECORD_SIZE)
        for i in range(page.count):
            chunk = page.records[i].pack()
            body[i * Song.RECORD_SIZE:(i + 1) * Song.RECORD_SIZE] = chunk

        with open(self.datafile, "r+b" if os.path.exists(self.datafile) else "wb") as f:
            f.seek(pos * DataPage.SIZE)
            f.write(header)
            f.write(body)

    def _alloc_page(self):
        size = os.path.getsize(self.datafile) if os.path.exists(self.datafile) else 0
        pos = size // DataPage.SIZE
        self._write_page(DataPage(), pos)
        return pos