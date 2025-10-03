import struct
import os
from typing import Tuple, Optional, List
from app.models.song import Song

# Configuración del B+ Tree
# R: Factor de bloque para nodos del índice (apuntadores)
# M: Factor de bloque para páginas de datos (registros)
#
# Con R=40, M=20:
# - Nodo índice: ~1.3KB (40 punteros + 39 claves)
# - Página datos: ~6.6KB (20 registros × 328 bytes)
# - Para 5000 registros: ~250 páginas, profundidad ≈ 2-3 niveles
#
# Ajustar según necesidades:
# - R más grande = árbol más plano pero nodos más grandes
# - M más grande = menos páginas pero más datos por página
R = 40  # Block Factor: Index (número de hijos por nodo)
M = 20  # Block Factor: Data (registros por página)
KEY_LEN = 30  # Longitud máxima de clave (track_id)
ENTRY_COUNT = R - 1  # Número de claves por nodo (R-1)


class Node:
    NODE_FMT = "?i" + ("30s" * ENTRY_COUNT) + ("i" * R)
    NODE_SIZE = struct.calcsize(NODE_FMT)

    def __init__(self, entries, children, is_last_level: bool, count: int):
        self.entries = entries if entries is not None else []
        self.children = children if children is not None else []
        self.is_last_level = is_last_level
        self.count = count


class DataPage:
    PAGE_HEADER_FMT = "ii"
    PAGE_HEADER_SIZE = struct.calcsize(PAGE_HEADER_FMT)
    PAGE_SIZE = PAGE_HEADER_SIZE + M * Song.RECORD_SIZE

    def __init__(self, records, count: int, next_page: int):
        self.records = records if records is not None else []
        self.count = count
        self.next_page = next_page


def search_in_page(records, count, key):
    for i in range(min(count, len(records))):
        r = records[i]
        if r and r.track_id == key:
            return r
    return None


class BPlusTreeFile:
    def __init__(self, filename: str, indexfile: str):
        self.filename = filename
        self.indexfile = indexfile

        if not os.path.exists(self.indexfile):
            root = Node(entries=[], children=[0] + [-1] * (R - 1), is_last_level=True, count=0)
            self.__write_node(root, 0)
        if not os.path.exists(self.filename):
            empty = DataPage(records=[], count=0, next_page=-1)
            self.__write_data_page(empty, 0)

    # ============ API ============
    def search(self, key: str):
        return self.__search_rec(key, 0)

    def rangeSearch(self, begin_key: str, end_key: str):
        return self.__range_search_rec(begin_key, end_key, 0)

    def add(self, song: Song):
        if not song.track_id or not song.track_id.strip():
            return

        leaf_node_pos, page_index, parent_stack = self.__descend_to_leaf(song.track_id)

        # Validar que page_index sea válido
        if page_index < 0:
            return

        page = self.__read_data_page(page_index)
        inserted, page = self.__insert_in_page_sorted(page, song)

        # CRÍTICO: Verificar ANTES de escribir si hay overflow
        if page.count > M:
            # Split primero, luego escribir
            self.__write_data_page(page, page_index)
            right_page_index, sep_key = self.__split_leaf(page_index)
            self.__insert_into_leaf_node(leaf_node_pos, sep_key, right_page_index, parent_stack)
        else:
            # Solo escribir si no hay overflow
            self.__write_data_page(page, page_index)

    def remove(self, key: str):
        leaf_pos, page_index, parent_stack = self.__descend_to_leaf(key)
        page = self.__read_data_page(page_index)

        old_first_key = page.records[0].track_id if page.count > 0 else None
        removed = False
        new_records = []
        for i in range(page.count):
            if page.records[i].track_id == key and not removed:
                removed = True
                continue
            new_records.append(page.records[i])

        if not removed:
            return False

        page.records = new_records
        page.count = len(new_records)
        self.__write_data_page(page, page_index)

        new_first_key = page.records[0].track_id if page.count > 0 else None
        if old_first_key != new_first_key and page.count > 0:
            self.__update_parent_separators(parent_stack, leaf_pos, old_first_key, new_first_key)
        return True

    # ============ Búsquedas ============
    def __search_rec(self, key: str, node_pos: int):
        node = self.__read_node(node_pos)
        pos = 0
        for i in range(node.count):
            if key >= node.entries[i]:
                pos += 1
            else:
                break

        if not node.is_last_level:
            child_pos = node.children[pos]
            if child_pos < 0:
                return None
            return self.__search_rec(key, child_pos)
        else:
            page_idx = node.children[pos]
            if page_idx < 0:
                return None
            page = self.__read_data_page(page_idx)
            return search_in_page(page.records, page.count, key)

    def __range_search_rec(self, begin_key: str, end_key: str, node_pos: int):
        node = self.__read_node(node_pos)
        pos = 0
        for i in range(node.count):
            if begin_key >= node.entries[i]:
                pos += 1
            else:
                break

        if not node.is_last_level:
            child_pos = node.children[pos]
            if child_pos < 0:
                return []
            return self.__range_search_rec(begin_key, end_key, child_pos)
        else:
            res = []
            page_idx = node.children[pos]
            while page_idx >= 0:
                page = self.__read_data_page(page_idx)
                for r in page.records[:page.count]:
                    if r.track_id < begin_key:
                        continue
                    if r.track_id > end_key:
                        return res
                    res.append(r)
                page_idx = page.next_page
            return res

    # ============ Auxiliares ============
    def __read_node(self, node_pos: int):
        with open(self.indexfile, "rb") as f:
            f.seek(node_pos * Node.NODE_SIZE)
            data = f.read(Node.NODE_SIZE)
        if not data or len(data) < Node.NODE_SIZE:
            return Node([], [-1] * R, False, 0)

        unpacked = struct.unpack(Node.NODE_FMT, data)
        is_last_level = bool(unpacked[0])
        count = int(unpacked[1])

        raw_keys = list(unpacked[2:2 + ENTRY_COUNT])
        children = list(unpacked[2 + ENTRY_COUNT:2 + ENTRY_COUNT + R])

        entries = []
        for i in range(min(count, ENTRY_COUNT)):
            key_str = raw_keys[i].decode(errors="ignore").rstrip("\x00").strip()
            if key_str:
                entries.append(key_str)

        if len(children) < R:
            children += [-1] * (R - len(children))
        elif len(children) > R:
            children = children[:R]

        return Node(entries, children, is_last_level, count)

    def __read_data_page(self, page_index: int):
        with open(self.filename, "rb") as f:
            f.seek(page_index * DataPage.PAGE_SIZE)
            header = f.read(DataPage.PAGE_HEADER_SIZE)
            if not header or len(header) < DataPage.PAGE_HEADER_SIZE:
                return DataPage([], 0, -1)
            count, next_page = struct.unpack(DataPage.PAGE_HEADER_FMT, header)
            raw = f.read(M * Song.RECORD_SIZE)

        records = []
        for i in range(M):
            start = i * Song.RECORD_SIZE
            end = (i + 1) * Song.RECORD_SIZE
            chunk = raw[start:end]
            if not chunk or len(chunk) < Song.RECORD_SIZE:
                break
            rec = Song.unpack(chunk)
            if rec:
                records.append(rec)

        count = max(0, min(count, M, len(records)))
        return DataPage(records[:count], count, next_page)

    def __write_data_page(self, page: DataPage, page_index: int):
        page.count = max(0, min(len(page.records), M))
        header = struct.pack(DataPage.PAGE_HEADER_FMT, page.count, page.next_page)

        body = bytearray(M * Song.RECORD_SIZE)
        for i in range(page.count):
            packed = page.records[i].pack()
            body[i * Song.RECORD_SIZE:(i + 1) * Song.RECORD_SIZE] = packed

        with open(self.filename, "r+b" if os.path.exists(self.filename) else "wb") as f:
            f.seek(page_index * DataPage.PAGE_SIZE)
            f.write(header)
            f.write(body)

    def __allocate_data_page(self) -> int:
        size = os.path.getsize(self.filename) if os.path.exists(self.filename) else 0
        pos = size // DataPage.PAGE_SIZE
        empty = DataPage([], 0, -1)
        self.__write_data_page(empty, pos)
        return pos

    def __descend_to_leaf(self, key: str):
        parent_stack = []
        node_pos = 0
        visited = set()

        while node_pos not in visited:
            visited.add(node_pos)
            node = self.__read_node(node_pos)

            pos = 0
            for i in range(node.count):
                if key >= node.entries[i]:
                    pos += 1
                else:
                    break

            # Validar que pos no exceda el rango
            if pos >= R or pos >= len(node.children):
                pos = min(pos, R - 1, len(node.children) - 1)

            if node.is_last_level:
                page_index = node.children[pos]
                return node_pos, page_index, parent_stack

            next_node = node.children[pos]
            if next_node < 0:
                # Hijo inválido, retornar el primero válido
                return node_pos, node.children[0], parent_stack

            parent_stack.append((node_pos, pos))
            node_pos = next_node

        # Loop detectado
        raise RuntimeError(f"Loop infinito detectado en __descend_to_leaf para key={key}")

    def __insert_in_page_sorted(self, page: DataPage, song: Song):
        # Evitar duplicado - actualizar
        for i in range(page.count):
            if page.records[i].track_id == song.track_id:
                page.records[i] = song
                return False, page

        # Insertar ordenado
        i = 0
        while i < page.count and page.records[i].track_id < song.track_id:
            i += 1
        page.records.insert(i, song)
        page.count = len(page.records)
        return True, page

    def __split_leaf(self, left_page_index: int):
        left = self.__read_data_page(left_page_index)

        # IMPORTANTE: Split debe hacerse DESPUÉS de que count > M
        # Dividir en dos mitades aproximadamente iguales
        mid = (left.count + 1) // 2

        right_records = left.records[mid:]
        left.records = left.records[:mid]
        left.count = len(left.records)

        # Crear nueva página a la derecha
        right_page_index = self.__allocate_data_page()
        right = DataPage(records=right_records, count=len(right_records), next_page=left.next_page)

        # Encadenar: left -> right -> (lo que seguía antes)
        left.next_page = right_page_index

        # Escribir ambas páginas
        self.__write_data_page(left, left_page_index)
        self.__write_data_page(right, right_page_index)

        # La clave separadora es la primera del lado derecho
        sep_key = right.records[0].track_id
        return right_page_index, sep_key

    def __split_last_level_node(self, node_pos: int):
        node = self.__read_node(node_pos)
        assert node.is_last_level

        # Solo tomar children válidos
        valid_children = node.children[:node.count + 1]

        mid = node.count // 2
        left_entries = node.entries[:mid]
        right_entries = node.entries[mid:]

        left_children = valid_children[:len(left_entries) + 1]
        right_children = valid_children[len(left_entries) + 1:]

        up_key = right_entries[0] if right_entries else ""

        left = Node(entries=left_entries,
                    children=left_children + [-1] * (R - len(left_children)),
                    is_last_level=True,
                    count=len(left_entries))
        right = Node(entries=right_entries,
                     children=right_children + [-1] * (R - len(right_children)),
                     is_last_level=True,
                     count=len(right_entries))

        self.__write_node(left, node_pos)
        right_pos = self.__allocate_node()
        self.__write_node(right, right_pos)
        return right_pos, up_key

    def __insert_into_leaf_node(self, leaf_node_pos: int, sep_key: str, right_page_index: int, parent_stack):
        node = self.__read_node(leaf_node_pos)

        if not node.is_last_level:
            raise RuntimeError(f"Se esperaba nodo hoja pero is_last_level=False en pos {leaf_node_pos}")

        # Encontrar posición de inserción
        pos = 0
        for i in range(node.count):
            if sep_key >= node.entries[i]:
                pos += 1
            else:
                break

        # Insertar en la posición correcta
        node.entries.insert(pos, sep_key)
        node.children.insert(pos + 1, right_page_index)
        node.count += 1

        # Normalizar children
        if len(node.children) > R:
            node.children = node.children[:R]
        while len(node.children) < R:
            node.children.append(-1)

        # Verificar overflow
        if node.count <= ENTRY_COUNT:
            # Truncar entries si es necesario
            if len(node.entries) > ENTRY_COUNT:
                node.entries = node.entries[:ENTRY_COUNT]
                node.count = ENTRY_COUNT
            self.__write_node(node, leaf_node_pos)
            return

        # Overflow: split del nodo
        right_node_pos, up_key = self.__split_last_level_node(leaf_node_pos)
        self.__insert_into_parent_node(parent_stack, leaf_node_pos, up_key, right_node_pos)

    def __insert_into_parent_node(self, parent_stack, left_node_pos: int, up_key: str, right_node_pos: int):
        if not parent_stack:
            # Crear nueva raíz: mover nodo actual y crear nueva raíz en pos 0
            # Primero, necesitamos mover el nodo left_node_pos si es la raíz (pos 0)
            if left_node_pos == 0:
                # Allocar nueva posición para el nodo izquierdo
                new_left_pos = self.__allocate_node()
                left_node = self.__read_node(0)
                self.__write_node(left_node, new_left_pos)
                left_node_pos = new_left_pos

            # Ahora crear nueva raíz en posición 0
            new_root = Node(entries=[up_key],
                            children=[left_node_pos, right_node_pos] + [-1] * (R - 2),
                            is_last_level=False,
                            count=1)
            self.__write_node(new_root, 0)
            return

        parent_pos, _slot = parent_stack.pop()
        parent = self.__read_node(parent_pos)

        # Encontrar posición
        insert_pos = 0
        for i in range(parent.count):
            if up_key >= parent.entries[i]:
                insert_pos += 1
            else:
                break

        parent.entries.insert(insert_pos, up_key)
        parent.children.insert(insert_pos + 1, right_node_pos)
        parent.count += 1

        # Normalizar
        if len(parent.children) > R:
            parent.children = parent.children[:R]
        else:
            parent.children += [-1] * (R - len(parent.children))

        if parent.count <= ENTRY_COUNT:
            if len(parent.entries) > ENTRY_COUNT:
                parent.entries = parent.entries[:ENTRY_COUNT]
                parent.count = ENTRY_COUNT
            self.__write_node(parent, parent_pos)
            return

        # Overflow: split interno
        self.__split_internal_and_propagate(parent_stack, parent_pos)

    def __split_internal_and_propagate(self, parent_stack, node_pos: int):
        node = self.__read_node(node_pos)

        mid_idx = node.count // 2
        up_key = node.entries[mid_idx]

        left_entries = node.entries[:mid_idx]
        left_children = node.children[:mid_idx + 1]
        left = Node(entries=left_entries,
                    children=left_children + [-1] * (R - len(left_children)),
                    is_last_level=False,
                    count=len(left_entries))

        right_entries = node.entries[mid_idx + 1:]
        right_children = node.children[mid_idx + 1:]
        right = Node(entries=right_entries,
                     children=right_children + [-1] * (R - len(right_children)),
                     is_last_level=False,
                     count=len(right_entries))

        self.__write_node(left, node_pos)
        right_pos = self.__allocate_node()
        self.__write_node(right, right_pos)

        self.__insert_into_parent(parent_stack, node_pos, up_key, right_pos)

    def __insert_into_parent(self, parent_stack, left_node_pos: int, sep_key: str, right_child_index: int):
        if not parent_stack:
            # Crear nueva raíz: necesitamos mover el nodo si está en posición 0
            if left_node_pos == 0:
                new_left_pos = self.__allocate_node()
                left_node = self.__read_node(0)
                self.__write_node(left_node, new_left_pos)
                left_node_pos = new_left_pos

            new_root = Node(entries=[sep_key],
                            children=[left_node_pos, right_child_index] + [-1] * (R - 2),
                            is_last_level=False,
                            count=1)
            self.__write_node(new_root, 0)
            return

        parent_pos, slot = parent_stack.pop()
        parent = self.__read_node(parent_pos)

        insert_pos = 0
        for i in range(parent.count):
            if sep_key >= parent.entries[i]:
                insert_pos += 1
            else:
                break

        parent.entries.insert(insert_pos, sep_key)
        parent.children.insert(insert_pos + 1, right_child_index)
        parent.count += 1

        if len(parent.children) > R:
            parent.children = parent.children[:R]
        else:
            parent.children += [-1] * (R - len(parent.children))

        if parent.count <= ENTRY_COUNT:
            if len(parent.entries) > ENTRY_COUNT:
                parent.entries = parent.entries[:ENTRY_COUNT]
                parent.count = ENTRY_COUNT
            self.__write_node(parent, parent_pos)
            return

        self.__split_internal_and_propagate(parent_stack, parent_pos)

    def __update_parent_separators(self, parent_stack: List[Tuple[int, int]], leaf_node_pos: int,
                                   old_first_key: Optional[str], new_first_key: Optional[str]):
        if not old_first_key or not new_first_key:
            return

        for (p_pos, _) in reversed(parent_stack):
            p = self.__read_node(p_pos)
            changed = False
            for i in range(p.count):
                if p.entries[i] == old_first_key:
                    p.entries[i] = new_first_key
                    changed = True
                    break
            if changed:
                self.__write_node(p, p_pos)
                return

    # ============ I/O nodos ============
    def __write_node(self, node: Node, node_pos: int):
        raw_keys = [b"\x00" * KEY_LEN for _ in range(ENTRY_COUNT)]
        for i in range(min(node.count, ENTRY_COUNT, len(node.entries))):
            kb = (node.entries[i] or "").encode()[:KEY_LEN]
            raw_keys[i] = kb + b"\x00" * (KEY_LEN - len(kb))

        children = (node.children[:R] + [-1] * R)[:R]
        packed = struct.pack(Node.NODE_FMT, bool(node.is_last_level), int(node.count), *raw_keys, *children)
        with open(self.indexfile, "r+b" if os.path.exists(self.indexfile) else "wb") as f:
            f.seek(node_pos * Node.NODE_SIZE)
            f.write(packed)

    def __allocate_node(self) -> int:
        size = os.path.getsize(self.indexfile) if os.path.exists(self.indexfile) else 0
        pos = size // Node.NODE_SIZE
        self.__write_node(Node([], [-1] * R, False, 0), pos)
        return pos