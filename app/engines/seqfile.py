import struct
import os
import math
from app.data.records.song import Song 

class SequentialFile:
    # Tamaño de un registro en el main se aumenta 1 byte para el boleano de borrado lógico
    MAIN_RECORD_SIZE = Song.RECORD_SIZE + 1

    def __init__(self, main_path: str, aux_path: str):
        self.main_path = main_path
        self.aux_path = aux_path

        if not os.path.exists(self.main_path):
            open(self.main_path, 'w').close()
        if not os.path.exists(self.aux_path):
            open(self.aux_path, 'w').close()

        self.main_file_handle = open(self.main_path, "r+b")
        self.aux_file_handle = open(self.aux_path, "r+b")

        # Umbral 'k' para la reconstrucción
        self.k_threshold = 10 # Inicio por defecto.

    def close(self):
        """Cierra de forma segura los manejadores de archivo para liberar recursos."""
        if hasattr(self, 'main_file_handle') and self.main_file_handle and not self.main_file_handle.closed:
            self.main_file_handle.close()
        if hasattr(self, 'aux_file_handle') and self.aux_file_handle and not self.aux_file_handle.closed:
            self.aux_file_handle.close()

    def __del__(self):
        """Destructor"""
        self.close()

    # ========== API Pública =================

    def add(self, song: Song):
        """Agrega una nueva canción al archivo auxiliar manteniendo el orden """
        aux_records = list(self._read_all_records_aux())
        aux_records.append(song)
        aux_records.sort(key=lambda s: s.track_id)
        
        self.aux_file_handle.seek(0)
        self.aux_file_handle.truncate()
        for s in aux_records:
            self.aux_file_handle.write(s.pack())
        self.aux_file_handle.flush()

        if len(aux_records) > self.k_threshold:
            print(f"--- Umbral k={self.k_threshold} superado. Reconstruyendo... ---")
            self._reconstruct()

    def search(self, key: str):
        """Busca una canción por su key usando búsqueda binaria en ambos archivos."""
        song, is_deleted = self._binary_search_main(key)
        if song:
            return song if not is_deleted else None

        aux_song = self._binary_search_aux(key)
        if aux_song:
            return aux_song
        
        return None

    def rangeSearch(self, begin_key: str, end_key: str):
        """Busca todas las canciones en un rango con una fusión O(N+K)."""
        main_results = []
        start_pos = self._find_first_in_range(begin_key)
        if start_pos != -1:
            self.main_file_handle.seek(start_pos * self.MAIN_RECORD_SIZE)
            while data := self.main_file_handle.read(self.MAIN_RECORD_SIZE):
                song, is_deleted = self._unpack_main_record(data)
                if song.track_id > end_key:
                    break
                if not is_deleted:
                    main_results.append(song)
        
        aux_results = [
            song for song in self._read_all_records_aux()
            if begin_key <= song.track_id <= end_key
        ]
        
        return self._merge_lists(main_results, aux_results)

    def remove(self, key: str):
        """
        - Borrado físico en el archivo auxiliar.
        - Borrado lógico en el archivo principal.
        """
        aux_records = list(self._read_all_records_aux())
        new_aux_records = [r for r in aux_records if r.track_id != key]

        if len(new_aux_records) < len(aux_records):
            self.aux_file_handle.seek(0)
            self.aux_file_handle.truncate()
            for record in new_aux_records:
                self.aux_file_handle.write(record.pack())
            self.aux_file_handle.flush()
            return True

        record_pos = self._find_record_pos(key)
        if record_pos != -1:
            self.main_file_handle.seek(record_pos * self.MAIN_RECORD_SIZE)
            packed_song_with_flag = self.main_file_handle.read(self.MAIN_RECORD_SIZE)
            if not packed_song_with_flag: return False 
            is_deleted = struct.unpack('?', packed_song_with_flag[-1:])[0]

            if not is_deleted:
                flag_position = record_pos * self.MAIN_RECORD_SIZE + Song.RECORD_SIZE
                self.main_file_handle.seek(flag_position)
                self.main_file_handle.write(struct.pack('?', True))
                self.main_file_handle.flush()
                
                self.main_file_handle.close()
                self.main_file_handle = open(self.main_path, "r+b")
                
                return True

        return False

    # ========== Métodos de Carga y Reconstrucción ==========

    def bulk_load(self, songs: list[Song]):
        """
        Carga masiva inicial. Ordena los datos y los escribe 
        en el archivo principal.
        """
        songs.sort(key=lambda s: s.track_id)
        
        self.main_file_handle.seek(0)
        self.main_file_handle.truncate()
        for song in songs:
            self.main_file_handle.write(song.pack() + struct.pack('?', False))
        self.main_file_handle.flush()
        
        self.aux_file_handle.seek(0)
        self.aux_file_handle.truncate()
        self.aux_file_handle.flush()

        n = len(songs)
        if n > 0:
            self.k_threshold = max(10, math.floor(math.log2(n)))
        print(f"Carga masiva completa. {n} registros cargados. Umbral k = {self.k_threshold}")

    def _reconstruct(self):
        """
        Fusiona el archivo principal y el auxiliar en un nuevo archivo principal ordenado.
        Complejidad O(N+K).
        """
        main_records = [
            song for song, is_deleted in self._read_all_records_main() if not is_deleted
        ]
        
        aux_records = list(self._read_all_records_aux())
        
        all_records = self._merge_lists(main_records, aux_records)

        self.bulk_load(all_records)
        print("Reconstrucción completa.")

    # ========== Métodos Internos de Ayuda ==========
    
    def _merge_lists(self, listA: list[Song], listB: list[Song]) -> list[Song]:
        """Algoritmo de fusión para combinar dos listas ya ordenadas."""
        merged_list = []
        ptrA, ptrB = 0, 0
        while ptrA < len(listA) and ptrB < len(listB):
            if listA[ptrA].track_id < listB[ptrB].track_id:
                merged_list.append(listA[ptrA])
                ptrA += 1
            else:
                merged_list.append(listB[ptrB])
                ptrB += 1
        merged_list.extend(listA[ptrA:])
        merged_list.extend(listB[ptrB:])
        return merged_list

    def _unpack_main_record(self, data: bytes):
        """Desempaqueta un registro del archivo principal en (Song, is_deleted)."""
        song_data = data[:Song.RECORD_SIZE]
        flag_data = data[Song.RECORD_SIZE:]
        song = Song.unpack(song_data)
        is_deleted = struct.unpack('?', flag_data)[0]
        return song, is_deleted

    def _read_all_records_main(self):
        """Generador que lee todos los registros del archivo principal."""
        self.main_file_handle.seek(0)
        while data := self.main_file_handle.read(self.MAIN_RECORD_SIZE):
            yield self._unpack_main_record(data)

    def _read_all_records_aux(self):
        """Generador que lee todos los registros del archivo auxiliar."""
        self.aux_file_handle.seek(0)
        while data := self.aux_file_handle.read(Song.RECORD_SIZE):
            yield Song.unpack(data)

    def _get_record_count_main(self):
        """Devuelve el número de registros en el archivo principal."""
        self.main_file_handle.seek(0, 2)
        return self.main_file_handle.tell() // self.MAIN_RECORD_SIZE

    def _get_record_count_aux(self):
        """Devuelve el número de registros en el archivo auxiliar."""
        self.aux_file_handle.seek(0, 2)
        return self.aux_file_handle.tell() // Song.RECORD_SIZE

    def _binary_search_main(self, key: str):
        """Búsqueda binaria en el archivo principal."""
        low, high = 0, self._get_record_count_main() - 1
        while low <= high:
            mid = (low + high) // 2
            self.main_file_handle.seek(mid * self.MAIN_RECORD_SIZE)
            data = self.main_file_handle.read(self.MAIN_RECORD_SIZE)
            if not data: continue
            song, is_deleted = self._unpack_main_record(data)
            
            if song.track_id == key:
                return song, is_deleted
            elif song.track_id < key:
                low = mid + 1
            else:
                high = mid - 1
        return None, None

    def _binary_search_aux(self, key: str):
        """Búsqueda binaria en el archivo auxiliar."""
        records = list(self._read_all_records_aux())
        low, high = 0, len(records) - 1
        while low <= high:
            mid = (low + high) // 2
            if records[mid].track_id == key:
                return records[mid]
            elif records[mid].track_id < key:
                low = mid + 1
            else:
                high = mid - 1
        return None

    def _find_record_pos(self, key: str):
        """Encuentra la posición de un registro en el archivo principal."""
        low, high = 0, self._get_record_count_main() - 1
        while low <= high:
            mid = (low + high) // 2
            self.main_file_handle.seek(mid * self.MAIN_RECORD_SIZE)
            data = self.main_file_handle.read(self.MAIN_RECORD_SIZE)
            if not data: continue
            song, _ = self._unpack_main_record(data)

            if song.track_id == key:
                return mid
            elif song.track_id < key:
                low = mid + 1
            else:
                high = mid - 1
        return -1 

    def _find_first_in_range(self, begin_key: str):
        """Encuentra la posición del primer registro cuyo ID es >= begin_key."""
        low, high = 0, self._get_record_count_main() - 1
        start_pos = -1
        while low <= high:
            mid = (low + high) // 2
            self.main_file_handle.seek(mid * self.MAIN_RECORD_SIZE)
            data = self.main_file_handle.read(self.MAIN_RECORD_SIZE)
            if not data: continue
            song, _ = self._unpack_main_record(data)
            
            if song.track_id >= begin_key:
                start_pos = mid
                high = mid - 1
            else:
                low = mid + 1
        return start_pos
