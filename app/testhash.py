#Creacion de .py para pruebas de hash
import struct
import os
import random
import time
import csv

from app.data.records.song import Song
from app.engines.extendiblehashing import ExtendibleHashingFile

# --- Constantes ---
CSV_FILE = 'app/data/datasets/spotify_songs.csv'
DATA_FILE = 'songs_unique_test.dat'
DIR_FILE = 'songs_unique_test.dir'

# --- Función Auxiliar para Cargar Datos ---

def load_songs_from_csv(filename, limit=None):
    songs = []
    print(f"Cargando hasta {limit or 'todos los'} registros desde {filename}...")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            unique_ids = set()
            for row in reader:
                if limit and len(songs) >= limit:
                    break
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
                        songs.append(song)
                        unique_ids.add(track_id)
                    except (ValueError, TypeError):
                        pass
    except FileNotFoundError:
        print(f"Error: El archivo '{filename}' no fue encontrado.")
        return None
    print(f"Carga completa. {len(songs)} registros únicos cargados.")
    return songs

# --- Funciones de Prueba ---

def test_basic_insertion_and_search():
    """Prueba la inserción y búsqueda básica usando la clave única 'track_id'."""
    print("\n--- INICIANDO PRUEBA: Inserción y Búsqueda con Clave Única ---")
    
    songs = load_songs_from_csv(CSV_FILE, limit=50)
    if not songs: return

    hash_index = ExtendibleHashingFile(DATA_FILE, DIR_FILE)
    
    for song in songs:
        hash_index.add(song)
    print(f"Se insertaron {len(songs)} canciones en el índice.")

    song_to_find = random.choice(songs)
    print(f"Buscando la canción con ID: {song_to_find.track_id} (Nombre: '{song_to_find.track_name}')")
    
    found_song = hash_index.search(song_to_find.track_id)
    
    assert found_song is not None, "Error: La canción no fue encontrada."
    assert found_song.track_id == song_to_find.track_id, "Error: El ID de la canción encontrada no coincide."
    assert found_song.track_name == song_to_find.track_name, "Error: El nombre de la canción encontrada no coincide."
    
    print(f"Éxito: La canción fue encontrada correctamente: {found_song}")
    
    print("Buscando una canción con un ID inexistente ('ID_FALSO_123')...")
    not_found_song = hash_index.search('ID_FALSO_123')
    assert not_found_song is None, "Error: Se encontró una canción que no debería existir."
    
    print("Éxito: La búsqueda de una clave inexistente devolvió None como se esperaba.")
    print("--- PRUEBA COMPLETADA ---")

def test_remove_and_update():
    """Prueba la eliminación y actualización de registros con clave única."""
    print("\n--- INICIANDO PRUEBA: Eliminación y Actualización ---")
    
    songs = load_songs_from_csv(CSV_FILE, limit=20)
    if not songs: return
    
    hash_index = ExtendibleHashingFile(DATA_FILE, DIR_FILE)
    
    for song in songs:
        hash_index.add(song)
        
    # 1. Prueba de eliminación
    song_to_remove = songs[5]
    print(f"Eliminando la canción: '{song_to_remove.track_name}' (ID: {song_to_remove.track_id})")
    
    remove_success = hash_index.remove(song_to_remove.track_id)
    assert remove_success, "Error: El método remove() devolvió False."
    
    found_song = hash_index.search(song_to_remove.track_id)
    assert found_song is None, "Error: La canción fue encontrada después de ser eliminada."
    print("Éxito: La canción fue eliminada correctamente.")
    
    # 2. Prueba de actualización (re-insertar con datos modificados)
    song_to_update = songs[10]
    song_to_update.track_popularity = 101
    print(f"Actualizando la popularidad de '{song_to_update.track_name}' a 101.")
    
    hash_index.add(song_to_update)
    
    found_updated_song = hash_index.search(song_to_update.track_id)
    assert found_updated_song is not None, "Error: La canción actualizada no fue encontrada."
    assert found_updated_song.track_popularity == 101, "Error: La popularidad de la canción no se actualizó."
    print(f"Éxito: La canción fue actualizada. Nueva popularidad: {found_updated_song.track_popularity}.")
    print("--- PRUEBA COMPLETADA ---")

def test_stress_splits():
    """Prueba de estrés insertando muchos registros para forzar splits y duplicaciones."""
    print("\n--- INICIANDO PRUEBA DE ESTRÉS: Splits con Claves Únicas ---")
    
    songs = load_songs_from_csv(CSV_FILE, limit=1000)
    if not songs: return

    hash_index = ExtendibleHashingFile(DATA_FILE, DIR_FILE)
    
    print(f"Insertando {len(songs)} registros para forzar la expansión...")
    for song in songs:
        hash_index.add(song)
    print("Inserción masiva completada.")

    print("Verificando la integridad de los datos después de múltiples splits...")
    songs_to_check = [songs[0], songs[len(songs) // 2], songs[-1]]
    
    for song_to_check in songs_to_check:
        found = hash_index.search(song_to_check.track_id)
        assert found is not None, f"Error CRÍTICO: La canción '{song_to_check.track_name}' no fue encontrada después del estrés."
        assert found.track_id == song_to_check.track_id, "Error CRÍTICO: La integridad de los datos se corrompió."
    
    print("Éxito: Canciones clave fueron encontradas correctamente después de la inserción masiva.")
    print("--- PRUEBA COMPLETADA ---")


# --- Ejecución Principal ---

if __name__ == "__main__":
    files_to_clean = [DATA_FILE, DIR_FILE]
    for f in files_to_clean:
        if os.path.exists(f): 
            os.remove(f)
            
    test_basic_insertion_and_search()
    test_remove_and_update()
    test_stress_splits()
    
    print("\nLimpiando archivos de prueba...")
    for f in files_to_clean:
        if os.path.exists(f): 
            os.remove(f)
    print("Limpieza completa.")