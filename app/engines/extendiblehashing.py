import struct
import os
from app.data.records.song import Song

# M es el Factor de Bloque 
M = 20

class Bucket:
    # Formato del Header: count, local_depth, next_overflow_bucket
    HEADER_FMT = "iii"
    HEADER_SIZE = struct.calcsize(HEADER_FMT)
    BUCKET_SIZE = HEADER_SIZE + M * Song.RECORD_SIZE

    def __init__(self, count=0, local_depth=1, next_overflow=-1):
        self.count = count
        self.local_depth = local_depth
        self.next_overflow = next_overflow
        self.records = []

class Directory:
    # Formato del Header: global_depth
    HEADER_FMT = "i"
    HEADER_SIZE = struct.calcsize(HEADER_FMT)

    def __init__(self, global_depth=2, pointers=None):
        self.global_depth = global_depth
        if pointers is None:
            self.pointers = [0, 1, 0, 1]
        else:
            self.pointers = pointers

class ExtendibleHashingFile:
    def __init__(self, datafile: str, dirfile: str):
        self.datafile = datafile
        self.dirfile = dirfile
        self._init_files()
        self.directory = self._read_directory()

    def _init_files(self):
        if not os.path.exists(self.dirfile):
            directory = Directory()
            self._write_directory(directory)
        if not os.path.exists(self.datafile):
            bucket0 = Bucket(local_depth=1)
            bucket1 = Bucket(local_depth=1)
            self._write_bucket(bucket0, 0)
            self._write_bucket(bucket1, 1)

    # ========== API Pública ==========

    def search(self, key: str):
        """Busca un registro por su clave usando el directorio en memoria."""
        bucket_pos = self._get_bucket_pos(key, self.directory)

        while bucket_pos != -1:
            bucket = self._read_bucket(bucket_pos)
            for record in bucket.records:
                if record.track_id == key:
                    return record
            bucket_pos = bucket.next_overflow
            
        return None

    def add(self, song: Song):
        """Agrega un nuevo registro de canción."""
        if not song.track_id:
            return

        # Usa el directorio en memoria para encontrar la posición.
        bucket_pos = self._get_bucket_pos(song.track_id, self.directory)
        self._add_to_bucket_chain(song, bucket_pos)

    def remove(self, key: str):
        """Elimina un registro por su clave."""
        bucket_pos = self._get_bucket_pos(key, self.directory)
        
        current_pos = bucket_pos
        while current_pos != -1:
            bucket = self._read_bucket(current_pos)
            
            record_to_remove = next((r for r in bucket.records if r.track_id == key), None)
            
            if record_to_remove:
                bucket.records.remove(record_to_remove)
                bucket.count -= 1
                self._write_bucket(bucket, current_pos)
                return True
                
            current_pos = bucket.next_overflow
            
        return False

    # ========== Métodos Internos ==========
    
    def _hash(self, key: str) -> int:
        return hash(key)

    def _get_bucket_pos(self, key: str, directory: Directory):
        h = self._hash(key)
        dir_idx = h & ((1 << directory.global_depth) - 1)
        return directory.pointers[dir_idx]

    def _add_to_bucket_chain(self, song: Song, bucket_pos: int):
        current_pos = bucket_pos
        last_bucket_pos = -1
        
        while current_pos != -1:
            bucket = self._read_bucket(current_pos)
            
            # Revisa si la canción ya existe para actualizarla
            for i, record in enumerate(bucket.records):
                if record.track_id == song.track_id:
                    bucket.records[i] = song 
                    self._write_bucket(bucket, current_pos)
                    return
            
            if bucket.count < M:
                bucket.records.append(song)
                bucket.count += 1
                self._write_bucket(bucket, current_pos)
                return

            last_bucket_pos = current_pos
            current_pos = bucket.next_overflow
            
        # Si llegamos aquí, toda la cadena está llena.
        tail_bucket = self._read_bucket(last_bucket_pos)
        self._handle_overflow(tail_bucket, last_bucket_pos, bucket_pos, song)

    def _handle_overflow(self, tail_bucket: Bucket, tail_bucket_pos: int, head_bucket_pos: int, song: Song):
        if tail_bucket.local_depth < self.directory.global_depth:
            self._split_bucket(head_bucket_pos, song)
        else:
            # Si el directorio está al máximo (d=D), primero duplicamos y luego reintentamos.
            if tail_bucket.local_depth == self.directory.global_depth:
                self._double_directory()
                # Después de duplicar, reintentamos la inserción desde el principio.
                self.add(song)
            else: # d < D, pero la política es añadir un bucket de overflow
                new_overflow_pos = self._alloc_bucket()
                new_bucket = Bucket(local_depth=tail_bucket.local_depth)
                new_bucket.records.append(song)
                new_bucket.count = 1
                self._write_bucket(new_bucket, new_overflow_pos)
                
                tail_bucket.next_overflow = new_overflow_pos
                self._write_bucket(tail_bucket, tail_bucket_pos)


    def _split_bucket(self, old_bucket_pos: int, new_song: Song):
        all_records_to_distribute = [new_song]
        current_pos = old_bucket_pos
        while current_pos != -1:
            b = self._read_bucket(current_pos)
            all_records_to_distribute.extend(b.records)
            current_pos = b.next_overflow

        old_bucket = self._read_bucket(old_bucket_pos)
        new_bucket_pos = self._alloc_bucket()
        new_bucket = Bucket(local_depth=old_bucket.local_depth + 1)
        
        old_bucket.local_depth += 1
        old_bucket.records = []
        old_bucket.count = 0
        old_bucket.next_overflow = -1
        
        # Actualizar punteros del directorio en memoria
        d = old_bucket.local_depth
        split_pattern = 1 << (d - 1)
        
        for i, ptr in enumerate(self.directory.pointers):
            if ptr == old_bucket_pos:
                if (i & split_pattern) != 0:
                    self.directory.pointers[i] = new_bucket_pos
        
        # Escribir el directorio actualizado al disco
        self._write_directory(self.directory)
        
        # Redistribución de todos los registros
        for record in all_records_to_distribute:
            # Usa el directorio actualizado en memoria para encontrar el nuevo destino
            target_pos = self._get_bucket_pos(record.track_id, self.directory)
            
            if target_pos == old_bucket_pos:
                old_bucket.records.append(record)
            else:
                new_bucket.records.append(record)

        old_bucket.count = len(old_bucket.records)
        new_bucket.count = len(new_bucket.records)
        
        self._write_bucket(old_bucket, old_bucket_pos)
        self._write_bucket(new_bucket, new_bucket_pos)

    def _double_directory(self):
        """Duplica el tamaño del directorio en memoria y lo escribe en disco."""
        self.directory.global_depth += 1
        self.directory.pointers.extend(self.directory.pointers)
        self._write_directory(self.directory)

    # ========== I/O ==========

    def _read_directory(self) -> Directory:
        if not os.path.exists(self.dirfile) or os.path.getsize(self.dirfile) == 0:
            return Directory()
            
        with open(self.dirfile, "rb") as f:
            header_data = f.read(Directory.HEADER_SIZE)
            global_depth = struct.unpack(Directory.HEADER_FMT, header_data)[0]
            num_pointers = 1 << global_depth
            pointers_fmt = "i" * num_pointers
            pointers_data = f.read(struct.calcsize(pointers_fmt))
            pointers = list(struct.unpack(pointers_fmt, pointers_data))
            
            return Directory(global_depth, pointers)

    def _write_directory(self, directory: Directory):
        with open(self.dirfile, "wb") as f:
            header = struct.pack(Directory.HEADER_FMT, directory.global_depth)
            f.write(header)
            
            pointers_fmt = "i" * len(directory.pointers)
            pointers_data = struct.pack(pointers_fmt, *directory.pointers)
            f.write(pointers_data)

    def _read_bucket(self, pos: int) -> Bucket:
        with open(self.datafile, "rb") as f:
            f.seek(pos * Bucket.BUCKET_SIZE)
            header_data = f.read(Bucket.HEADER_SIZE)
            if len(header_data) < Bucket.HEADER_SIZE: return Bucket()

            count, local_depth, next_overflow = struct.unpack(Bucket.HEADER_FMT, header_data)
            bucket = Bucket(count, local_depth, next_overflow)
            
            raw_records = f.read(M * Song.RECORD_SIZE)
            for i in range(count):
                start = i * Song.RECORD_SIZE
                end = start + Song.RECORD_SIZE
                song = Song.unpack(raw_records[start:end])
                if song:
                    bucket.records.append(song)
            
            return bucket

    def _write_bucket(self, bucket: Bucket, pos: int):
        with open(self.datafile, "r+b" if os.path.exists(self.datafile) else "wb") as f:
            f.seek(pos * Bucket.BUCKET_SIZE)
            header = struct.pack(Bucket.HEADER_FMT, bucket.count, bucket.local_depth, bucket.next_overflow)
            f.write(header)
            
            body = bytearray(M * Song.RECORD_SIZE)
            for i in range(bucket.count):
                chunk = bucket.records[i].pack()
                body[i * Song.RECORD_SIZE:(i + 1) * Song.RECORD_SIZE] = chunk
            f.write(body)

    def _alloc_bucket(self) -> int:
        size = os.path.getsize(self.datafile) if os.path.exists(self.datafile) else 0
        pos = size // Bucket.BUCKET_SIZE
        self._write_bucket(Bucket(), pos)
        return pos