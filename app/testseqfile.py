import os
import random
import csv
from app.data.records.song import Song
from app.engines.seqfile import SequentialFile 

CSV_FILE = 'app/data/datasets/spotify_songs.csv'
MAIN_FILE = 'songs_main_test.dat'
AUX_FILE = 'songs_aux_test.dat'

def cleanup_files():
    """Función auxiliar para borrar los archivos de prueba."""
    for f in [MAIN_FILE, AUX_FILE]:
        if os.path.exists(f):
            os.remove(f)

def load_songs_from_csv(filename, limit=None):
    """Carga canciones desde un archivo CSV, asegurando IDs únicos."""
    songs = []
    print(f"Cargando hasta {limit or 'todos los'} registros desde {filename}...")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            unique_ids = set()
            for row in reader:
                if limit and len(songs) >= limit: break
                track_id = row.get('track_id', '')
                if track_id and track_id not in unique_ids:
                    try:
                        song = Song(
                            track_id=track_id, track_name=row.get('track_name', ''),
                            track_artist=row.get('track_artist', ''), track_popularity=int(row.get('track_popularity', 0)),
                            track_album_id=row.get('track_album_id', ''), track_album_name=row.get('track_album_name', ''),
                            track_album_release_date=row.get('track_album_release_date', ''),
                            acousticness=float(row.get('acousticness', 0.0)),
                            instrumentalness=float(row.get('instrumentalness', 0.0)),
                            duration_ms=int(row.get('duration_ms', 0))
                        )
                        songs.append(song); unique_ids.add(track_id)
                    except (ValueError, TypeError): pass
    except FileNotFoundError:
        print(f"Error CRÍTICO: El archivo CSV '{filename}' no fue encontrado.")
        return []
    print(f"Carga completa. {len(songs)} registros únicos cargados.")
    return songs

# --- Funciones de Prueba ---

def test_bulk_load_and_binary_search():
    """Prueba la carga masiva y la búsqueda binaria en ambos archivos."""
    cleanup_files() 
    print("\n--- INICIANDO PRUEBA: Carga Masiva y Búsqueda Binaria ---")
    
    songs = load_songs_from_csv(CSV_FILE, limit=100)
    if not songs: return

    seq_file = SequentialFile(MAIN_FILE, AUX_FILE)
    seq_file.bulk_load(songs)
    
    song_to_find = random.choice(songs)
    print(f"Buscando en archivo principal: '{song_to_find.track_name}'...")
    found_song = seq_file.search(song_to_find.track_id)
    assert found_song is not None and found_song.track_id == song_to_find.track_id
    print("Éxito: La canción fue encontrada correctamente en el archivo principal.")

    new_song = Song("TEST001", "Test Song Aux", "Test Artist", 50, "ALB001", "Test Album", "2023-01-01", 0.5, 0.5, 200000)
    seq_file.add(new_song)
    print(f"Buscando en archivo auxiliar: '{new_song.track_name}'...")
    found_in_aux = seq_file.search("TEST001")
    assert found_in_aux is not None and found_in_aux.track_name == "Test Song Aux"
    print("Éxito: La canción fue encontrada correctamente en el archivo auxiliar.")

    print("Buscando una canción con un ID inexistente ('ID_FALSO_123')...")
    not_found_song = seq_file.search('ID_FALSO_123')
    assert not_found_song is None
    print("Éxito: La búsqueda de una clave inexistente devolvió None.")

    seq_file.close()
    print("--- PRUEBA COMPLETADA ---")

def test_add_maintains_order():
    """Prueba clave: Verifica que el método 'add' mantiene el archivo auxiliar ordenado."""
    cleanup_files() 
    print("\n--- INICIANDO PRUEBA: 'add' Mantiene el Orden del Auxiliar ---")
    seq_file = SequentialFile(MAIN_FILE, AUX_FILE)
    
    song1 = Song("C_SONG", "Song C", "Artist", 1, "", "", "", 0, 0, 0)
    song2 = Song("A_SONG", "Song A", "Artist", 1, "", "", "", 0, 0, 0)
    song3 = Song("B_SONG", "Song B", "Artist", 1, "", "", "", 0, 0, 0)
    
    print("Insertando canciones en el auxiliar en el orden: C, A, B...")
    seq_file.add(song1)
    seq_file.add(song2)
    seq_file.add(song3)

    aux_ids = [s.track_id for s in seq_file._read_all_records_aux()]
    print(f"Orden real en el archivo auxiliar: {aux_ids}")
    expected_order = ["A_SONG", "B_SONG", "C_SONG"]
    
    assert aux_ids == expected_order, "Error CRÍTICO: El método 'add' no mantuvo el archivo auxiliar ordenado."
    print("Éxito: El archivo auxiliar se mantiene correctamente ordenado.")
    
    seq_file.close()
    print("--- PRUEBA COMPLETADA ---")

def test_remove():
    """Prueba el borrado lógico en el principal y el físico en el auxiliar."""
    cleanup_files() 
    print("\n--- INICIANDO PRUEBA: Eliminación Lógica y Física ---")
    
    songs = load_songs_from_csv(CSV_FILE, limit=50)
    if not songs: return
    
    seq_file = SequentialFile(MAIN_FILE, AUX_FILE)
    seq_file.bulk_load(songs)
    
    song_to_remove_main = songs[25]
    print(f"Eliminando lógicamente: '{song_to_remove_main.track_name}'...")
    assert seq_file.remove(song_to_remove_main.track_id)
    assert seq_file.search(song_to_remove_main.track_id) is None
    print("Éxito: La canción fue eliminada lógicamente.")

    song_aux_1 = Song("AUX_001", "Aux Song 1", "Aux Artist", 99, "", "", "", 0, 0, 0)
    song_aux_2 = Song("AUX_002", "Aux Song 2", "Aux Artist", 99, "", "", "", 0, 0, 0)
    seq_file.add(song_aux_1); seq_file.add(song_aux_2)
    
    print(f"Eliminando físicamente del auxiliar: '{song_aux_1.track_name}'...")
    assert seq_file.remove(song_aux_1.track_id)
    assert seq_file.search("AUX_001") is None
    assert seq_file._get_record_count_aux() == 1
    print("Éxito: La canción fue eliminada físicamente del archivo auxiliar.")

    seq_file.close()
    print("--- PRUEBA COMPLETADA ---")

def test_range_search_with_merge():
    """Prueba la búsqueda por rango, verificando la correcta fusión de ambos archivos."""
    cleanup_files() 
    print("\n--- INICIANDO PRUEBA: Búsqueda por Rango con Fusión Ordenada ---")
    
    songs = sorted(load_songs_from_csv(CSV_FILE, limit=100), key=lambda s: s.track_id)
    if not songs: return

    seq_file = SequentialFile(MAIN_FILE, AUX_FILE)
    seq_file.bulk_load(songs)

    song_in_aux = Song(songs[15].track_id + "Z", 'Cancion Auxiliar en Rango', 'Artista Aux', 88, '', '', '', 0, 0, 0)
    seq_file.add(song_in_aux)

    start_key, end_key = songs[10].track_id, songs[20].track_id
    print(f"Buscando en el rango de ID: [{start_key}, {end_key}]")
    results = seq_file.rangeSearch(start_key, end_key)
    
    expected_count = 11 + 1 # 11 del principal (índices 10-20) + 1 del auxiliar
    assert len(results) == expected_count
    
    result_ids = [r.track_id for r in results]
    assert result_ids == sorted(result_ids) and song_in_aux.track_id in result_ids
    print(f"Éxito: Se encontraron {len(results)} canciones y la fusión las mantuvo ordenadas.")
    seq_file.close()
    print("--- PRUEBA COMPLETADA ---")

def test_reconstruction_stress():
    """Prueba de estrés que fuerza la reconstrucción y verifica la integridad final."""
    cleanup_files() 
    print("\n--- INICIANDO PRUEBA DE ESTRÉS: Reconstrucción Automática ---")
    
    songs = load_songs_from_csv(CSV_FILE, limit=None)
    if not songs: return

    seq_file = SequentialFile(MAIN_FILE, AUX_FILE)
    seq_file.bulk_load(songs)
    print(f"El umbral de reconstrucción 'k' es: {seq_file.k_threshold}")

    song_to_remove_1, song_to_remove_2 = songs[5], songs[15]
    seq_file.remove(song_to_remove_1.track_id); seq_file.remove(song_to_remove_2.track_id)
    print(f"Eliminadas lógicamente '{song_to_remove_1.track_name}' y '{song_to_remove_2.track_name}'.")

    print(f"Añadiendo {seq_file.k_threshold + 1} canciones para disparar la reconstrucción...")
    for i in range(seq_file.k_threshold + 1):
        seq_file.add(Song(f"NEW_ID_{i:03d}", f"New Song {i}", "Stress Artist", 50, "", "", "", 0, 0, 0))

    assert seq_file._get_record_count_aux() == 0, "Fallo: El auxiliar no está vacío."
    print("Éxito: El archivo auxiliar fue vaciado.")

    expected_size = len(songs) - 2 + (seq_file.k_threshold + 1)
    assert seq_file._get_record_count_main() == expected_size, "Fallo: Tamaño del principal incorrecto."
    print(f"Éxito: El tamaño del archivo principal es correcto ({expected_size} registros).")
    
    assert seq_file.search(song_to_remove_1.track_id) is None, "Fallo: Canción eliminada aún existe."
    print("Éxito: Las canciones eliminadas fueron purgadas.")

    last_added_song_id = f"NEW_ID_{seq_file.k_threshold:03d}"
    assert seq_file.search(last_added_song_id) is not None, "Fallo: Canción nueva no encontrada."
    print("Éxito: Las nuevas canciones fueron integradas.")
    
    seq_file.close()
    print("--- PRUEBA COMPLETADA ---")

# --- Ejecución Principal ---

if __name__ == "__main__":
    # Ejecutar todas las pruebas
    test_bulk_load_and_binary_search()
    test_add_maintains_order()
    test_remove()
    test_range_search_with_merge()
    test_reconstruction_stress()
    
    # Limpiar los archivos una última vez al final de toda la ejecución.
    print("\nLimpiando archivos de prueba...")
    cleanup_files()
    print("Limpieza completa.")