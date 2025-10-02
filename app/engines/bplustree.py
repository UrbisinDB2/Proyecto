import struct
import os, csv
from re import search

from app.models.song import Song

R = 4 # Block Factor: Index
M = 4 # Block Factor: Data
KEY_LEN = 30
ENTRY_COUNT = R - 1

class Node:
    NODE_FMT = "?i" + ("30s" * ENTRY_COUNT) + ("i" * R)
    NODE_SIZE = struct.calcsize(NODE_FMT)

    def __init__(self, entries, children, is_last_level : bool, count : int):
        self.entries = entries if entries is not None else []
        self.children = children if children is not None else []
        self.is_last_level = is_last_level
        self.count = count

class DataPage:
    PAGE_HEADER_FMT = "ii"
    PAGE_HEADER_SIZE = struct.calcsize(PAGE_HEADER_FMT)
    PAGE_SIZE = PAGE_HEADER_SIZE + M * Song.RECORD_SIZE

    def __init__(self, records, count : int, next_page : int):
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
    def __init__(self, filename : str, indexfile : str):
        self.filename = filename
        self.indexfile = indexfile

    # Main methods
    def search(self, key : str):
        return self.__search_rec(key, 0)

    def rangeSearch(self, begin_key : str, end_key : str):
        return self.__range_search_rec(begin_key, end_key, 0)

    def add(self, song : Song):
        pass

    def remove(self, key : str):
        pass

    # Private Methods

    def __search_rec(self, key : str, node_pos : int):
        node = self.__read_node(node_pos)

        pos = 0
        for i in range(node.count):
            if key >= node.entries[i]:
                pos += 1
            else:
                break

        if not node.is_last_level:
            return self.__search_rec(key, pos)
        else:
            page = self.__read_data_page( node.children[pos])
            record = search_in_page(page.records, page.count, key)
            return record

    def __range_search_rec(self, begin_key : str, end_key : str, node_pos : int):
        records = []
        node = self.__read_node(node_pos)

        pos = 0
        for i in range(node.count):
            if begin_key >= node.entries[i]:
                pos += 1
            else:
                break

        if not node.is_last_level:
            return self.__search_rec(begin_key, pos)
        else:
            page = self.__read_data_page(node.children[pos])
            for i in range(page.count):
                if page.next_page != -1:
                    page = self.__pass_page(page.next_page)
                else:
                    record = search_in_page(page.records, page.count, begin_key)
                    if record and end_key <= record.track_id:
                        records.append(record)
            return records

    # Aux Methods

    def __read_node(self, node_pos : int):
        with open(self.filename, "rb") as file:
            file.seek(node_pos * Node.NODE_SIZE)
            data = file.read(Node.NODE_SIZE)
        if not data or len(data) < Node.NODE_SIZE:
            return Node([], [], False, 0)
        unpacked = struct.unpack(Node.NODE_FMT, data)
        is_last_level = unpacked[0]
        count = unpacked[1]
        raw_keys = unpacked[2:2 + ENTRY_COUNT]
        children = unpacked[2 + ENTRY_COUNT:]
        entries = []
        for i in range(min(count, ENTRY_COUNT)):
            entries.append(raw_keys[i].decode(errors="ignore").strip("\x00").strip())
        return Node(entries, children, is_last_level, count)

    def __read_data_page(self, page_index):
        with open(self.filename, "rb") as file:
            file.seek(page_index * DataPage.PAGE_SIZE)
            header = file.read(DataPage.PAGE_HEADER_SIZE)
            if not header or len(header) < DataPage.PAGE_HEADER_SIZE:
                return DataPage([], 0, -1)
            count, next_page = struct.unpack(DataPage.PAGE_HEADER_FMT, header)
            raw = file.read(M * Song.RECORD_SIZE)
        records = []
        for i in range(M):
            chunk = raw[i * Song.RECORD_SIZE:(i + 1) * Song.RECORD_SIZE]
            if not chunk or len(chunk) < Song.RECORD_SIZE:
                break
            s = Song.unpack(chunk)
            records.append(s)
        records = records[:count]
        return DataPage(records, count, next_page * max(1, count))

    def __pass_page(self, next_index):
        if next_index is None or next_index < 0:
            return DataPage([], 0, -1)
        return self.__read_data_page(next_index)