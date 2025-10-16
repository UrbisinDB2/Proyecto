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
            # Estado inicial: D=2, 2 buckets. Punteros 00 y 10 -> bucket 0; 01 y 11 -> bucket 1
            self.pointers = [0, 1, 0, 1]
        else:
            self.pointers = pointers

class ExtendibleHashingFile:
    def __init__(self, datafile: str, dirfile: str, index_key: str = 'track_id'):
        self.datafile = datafile
        self.dirfile = dirfile
        self.index_key = index_key
        self._init_files()

    def _init_files(self):
        if not os.path.exists(self.dirfile):
            directory = Directory()
            self._write_directory(directory)
        if not os.path.exists(self.datafile):
            # Crear los dos buckets iniciales
            bucket0 = Bucket(local_depth=1)
            bucket1 = Bucket(local_depth=1)
            self._write_bucket(bucket0, 0)
            self._write_bucket(bucket1, 1)

    # ========== API Pública ==========

    def search(self, key: str):
        """Busca un registro por su clave"""
        directory = self._read_directory()
        bucket_pos = self._get_bucket_pos(key, directory)

        while bucket_pos != -1:
            bucket = self._read_bucket(bucket_pos)
            for record in bucket.records:
                record_key = getattr(record, self.index_key)
                if record.track_id == key:
                    return record
            bucket_pos = bucket.next_overflow
            
        return None

    def add(self, song: Song):
        """Agrega un nuevo registro de canción."""
        key_value = getattr(song, self.index_key)
        if not song.track_id:
            return

        directory = self._read_directory()
        bucket_pos = self._get_bucket_pos(song.track_id, directory)
        
        self._add_to_bucket_chain(song, bucket_pos, directory)

    def remove(self, key: str):
        """Elimina un registro por su clave"""
        directory = self._read_directory()
        bucket_pos = self._get_bucket_pos(key, directory)
        
        current_pos = bucket_pos
        prev_pos = -1
        prev_bucket = None

        while current_pos != -1:
            bucket = self._read_bucket(current_pos)
            
            record_to_remove = None
            for record in bucket.records:
                record_key = getattr(record, self.index_key)
                if record_key == key:
                    record_to_remove = record
                    break
            
            if record_to_remove:
                bucket.records.remove(record_to_remove)
                bucket.count -= 1
                self._write_bucket(bucket, current_pos)
                return True
                
            prev_pos = current_pos
            prev_bucket = bucket
            current_pos = bucket.next_overflow
            
        return False

    # ========== Métodos Internos ==========
    
    def _hash(self, key: str) -> int:
        """Función hash simple para la clave."""
        return hash(key)

    def _get_bucket_pos(self, key: str, directory: Directory):
        """Obtiene la posición del bucket en el archivo de datos a partir de la clave."""
        h = self._hash(key)
        # Tomar los ultimos 'global_depth' bits
        dir_idx = h & ((1 << directory.global_depth) - 1)
        return directory.pointers[dir_idx]

    def _add_to_bucket_chain(self, song: Song, bucket_pos: int, directory: Directory):
        """Intenta agregar una canción a un bucket o su cadena de desbordamiento."""
        current_pos = bucket_pos
        last_bucket = None
        last_bucket_pos = -1 # Necesitamos la posición del último bucket
        song_key = getattr(song, self.index_key)
        
        while current_pos != -1:
            bucket = self._read_bucket(current_pos)
            
            for i, record in enumerate(bucket.records):
                if getattr(record, self.index_key) == song_key:
                    bucket.records[i] = song 
                    self._write_bucket(bucket, current_pos)
                    return
            
            if bucket.count < M:
                bucket.records.append(song)
                bucket.count += 1
                self._write_bucket(bucket, current_pos)
                return

            last_bucket = bucket
            last_bucket_pos = current_pos
            current_pos = bucket.next_overflow
            
        # Pasamos el último bucket y la posición de la cabeza de la cadena
        self._handle_overflow(last_bucket, last_bucket_pos, bucket_pos, song, directory)

    def _handle_overflow(self, tail_bucket: Bucket, tail_bucket_pos: int, head_bucket_pos: int, song: Song, directory: Directory):
        """Maneja el desbordamiento de un bucket."""
        if tail_bucket.local_depth < directory.global_depth:
            # Siempre dividimos la cabeza de la cadena para mantener la estructura
            self._split_bucket(head_bucket_pos, song, directory)
        else:
            # La lógica de overflow/duplicación se aplica al final de la cadena
            if tail_bucket.next_overflow == -1:
                new_overflow_pos = self._alloc_bucket()
                new_bucket = Bucket(local_depth=tail_bucket.local_depth)
                new_bucket.records.append(song)
                new_bucket.count = 1
                self._write_bucket(new_bucket, new_overflow_pos)
                
                tail_bucket.next_overflow = new_overflow_pos
                self._write_bucket(tail_bucket, tail_bucket_pos)
            else:
                self._double_directory()
                self.add(song)

    def _split_bucket(self, old_bucket_pos: int, new_song: Song, directory: Directory):
        """
        Divide un bucket y redistribuye TODOS sus registros (incluyendo la cadena de desbordamiento).
        """
        # Recolectar registros de TODA la cadena de desbordamiento.
        all_records_to_distribute = [new_song]
        current_pos = old_bucket_pos
        while current_pos != -1:
            b = self._read_bucket(current_pos)
            all_records_to_distribute.extend(b.records)
            current_pos = b.next_overflow

        # Lógica de división sobre la lista completa
        old_bucket = self._read_bucket(old_bucket_pos)
        new_bucket_pos = self._alloc_bucket()
        new_bucket = Bucket(local_depth=old_bucket.local_depth + 1)
        
        old_bucket.local_depth += 1
        
        # Limpiar el bucket original y romper la vieja cadena de desbordamiento
        old_bucket.records = []
        old_bucket.count = 0
        old_bucket.next_overflow = -1
        
        # Actualizar punteros del directorio
        d = old_bucket.local_depth
        split_pattern = 1 << (d - 1)
        
        current_directory = self._read_directory()
        for i in range(len(current_directory.pointers)):
            if current_directory.pointers[i] == old_bucket_pos:
                if i & split_pattern:
                    current_directory.pointers[i] = new_bucket_pos

        self._write_directory(current_directory)
        
        # Redistribución de todos los registros
        for record in all_records_to_distribute:
            key_value = getattr(record, self.index_key)
            target_pos = self._get_bucket_pos(key_value, current_directory)

            # Asignar al bucket correcto
            target_bucket = old_bucket if target_pos == old_bucket_pos else new_bucket
            
            # Verificar si el bucket al que se reasigna está lleno y crear un overflow si es necesario
            if len(target_bucket.records) < M:
                target_bucket.records.append(record)
            else:
                temp_pos = self._alloc_bucket()
                temp_bucket = Bucket(local_depth=target_bucket.local_depth)
                temp_bucket.records.append(record)
                temp_bucket.count = 1
                self._write_bucket(temp_bucket, temp_pos)
                
                # Encontrar el final de la nueva cadena y añadirlo
                final_bucket = target_bucket
                while final_bucket.next_overflow != -1:
                    final_bucket = self._read_bucket(final_bucket.next_overflow)
                final_bucket.next_overflow = temp_pos

        # Actualizar contadores y escribir en disco
        old_bucket.count = len(old_bucket.records)
        new_bucket.count = len(new_bucket.records)
        
        self._write_bucket(old_bucket, old_bucket_pos)
        self._write_bucket(new_bucket, new_bucket_pos)

    def _double_directory(self):
        """Duplica el tamaño del directorio cuando d=D."""
        directory = self._read_directory()
        directory.global_depth += 1
        # Duplica la lista de punteros
        directory.pointers.extend(directory.pointers)
        self._write_directory(directory)

    # ========== I/O ==========

    def _read_directory(self) -> Directory:
        if not os.path.exists(self.dirfile):
            return Directory()
            
        with open(self.dirfile, "rb") as f:
            header_data = f.read(Directory.HEADER_SIZE)
            if not header_data: return Directory()
            
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
            if not header_data: return Bucket()

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
        """Asigna espacio para un nuevo bucket y devuelve su posición."""
        size = os.path.getsize(self.datafile) if os.path.exists(self.datafile) else 0
        pos = size // Bucket.BUCKET_SIZE
        # Escribimos un bucket vacío para asegurar que el archivo crezca
        self._write_bucket(Bucket(), pos)
        return pos