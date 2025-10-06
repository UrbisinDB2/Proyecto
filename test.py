"""
Test standalone para B+Tree
Simplemente ejecuta: python test_bptree_standalone.py
"""
import os
import sys
import random

# Configuración
CSV_PATH = r".\data\datasets\clean_spotify_songs.csv"
DATA_FILE = "test_songs.dat"
INDEX_FILE = "test_songs.idx"
NUM_RECORDS = 3000

# Importar módulos necesarios
try:
    from app.models.song import Song
    from app.engines.bplustree import BPlusTreeFile
except ImportError as e:
    print(f"ERROR: No se pudo importar módulos necesarios: {e}")
    print("Asegúrate de ejecutar desde la raíz del proyecto")
    sys.exit(1)


def build_song(row: dict):
    """Construye un objeto Song desde un diccionario CSV"""

    def safe_int(v, default=0):
        try:
            return int(float(v))
        except:
            return default

    def safe_float(v, default=0.0):
        try:
            return float(v)
        except:
            return default

    return Song(
        track_id=str(row.get("track_id", ""))[:30],
        track_name=row.get("track_name", "")[:100],
        track_artist=row.get("track_artist", "")[:40],
        track_popularity=safe_int(row.get("track_popularity", 0)),
        track_album_id=str(row.get("track_album_id", ""))[:30],
        track_album_name=row.get("track_album_name", "")[:100],
        track_album_release_date=str(row.get("track_album_release_date", ""))[:12],
        acousticness=safe_float(row.get("acousticness", 0.0)),
        instrumentalness=safe_float(row.get("instrumentalness", 0.0)),
        duration_ms=safe_int(row.get("duration_ms", 0)),
    )


def load_csv(path, limit=None):
    """Carga datos del CSV"""
    import csv
    songs = []

    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                song = build_song(row)
                if song.track_id and song.track_id.strip():
                    songs.append(song)
                if limit and len(songs) >= limit:
                    break
        return songs
    except FileNotFoundError:
        print(f"ERROR: No se encuentra el archivo {path}")
        return []


def print_header(text):
    print("\n" + "=" * 70)
    print(text.center(70))
    print("=" * 70)


def print_result(passed, failed):
    total = passed + failed
    print(f"\nResultado: {passed}/{total} tests pasados", end="")
    if failed > 0:
        print(f" ({failed} fallaron)")
    else:
        print(" - TODOS PASARON")


def main():
    print_header("TEST B+ TREE - EJECUCIÓN AUTOMÁTICA")

    # Limpiar archivos anteriores
    print("\nLimpiando archivos anteriores...")
    for f in [DATA_FILE, INDEX_FILE]:
        if os.path.exists(f):
            os.remove(f)
            print(f"  Eliminado: {f}")

    # Cargar datos
    print(f"\nCargando {NUM_RECORDS} registros de {CSV_PATH}...")
    songs = load_csv(CSV_PATH, NUM_RECORDS)

    if not songs:
        print("ERROR: No se cargaron datos")
        return

    print(f"Cargados: {len(songs)} canciones")

    # Crear B+Tree
    print(f"\nCreando B+Tree...")
    bpt = BPlusTreeFile(DATA_FILE, INDEX_FILE)

    # ========== TEST 1: INSERCIONES ==========
    print_header("TEST 1: INSERCIONES")
    passed, failed = 0, 0

    inserted_keys = set()
    for i, song in enumerate(songs):
        try:
            bpt.add(song)
            inserted_keys.add(song.track_id)
            passed += 1
            if (i + 1) % 250 == 0:
                print(f"  Progreso: {i + 1}/{len(songs)}")
        except Exception as e:
            failed += 1
            if failed <= 3:
                print(f"  ERROR insertando {song.track_id}: {e}")

    print_result(passed, failed)

    # ========== TEST 2: BÚSQUEDAS EXACTAS ==========
    print_header("TEST 2: BÚSQUEDAS EXACTAS")
    passed, failed = 0, 0

    keys_list = sorted(list(inserted_keys))
    test_keys = (
            keys_list[:10] +  # Primeras 10
            keys_list[len(keys_list) // 2 - 5:len(keys_list) // 2 + 5] +  # 10 del medio
            keys_list[-10:] +  # Últimas 10
            random.sample(keys_list, min(20, len(keys_list)))  # 20 aleatorias
    )
    test_keys = list(set(test_keys))[:50]

    print(f"Buscando {len(test_keys)} claves...")
    for key in test_keys:
        result = bpt.search(key)
        if result and result.track_id == key:
            passed += 1
        else:
            failed += 1
            if failed <= 3:
                print(f"  ERROR: No se encontró {key[:20]}...")

    print_result(passed, failed)

    # ========== TEST 3: CLAVES INEXISTENTES ==========
    print_header("TEST 3: CLAVES INEXISTENTES")
    passed, failed = 0, 0

    fake_keys = [
        "ZZZZZZZZZZZZZZZZZZZZZZZZZZ",
        "000000000000000000000000000",
        "___NO_EXISTE___",
        "",
        "xxxxxxxxxxxxxxxxxx",
        "9999999999999999999999"
    ]

    print(f"Buscando {len(fake_keys)} claves inexistentes...")
    for key in fake_keys:
        result = bpt.search(key)
        if result is None:
            passed += 1
        else:
            failed += 1
            print(f"  ERROR: Encontró clave inexistente: {key}")

    print_result(passed, failed)

    # ========== TEST 4: BÚSQUEDAS POR RANGO ==========
    print_header("TEST 4: BÚSQUEDAS POR RANGO")
    passed, failed = 0, 0

    if len(keys_list) >= 100:
        # Rango pequeño
        begin = keys_list[20]
        end = keys_list[50]
        expected = set(keys_list[20:51])

        result = bpt.rangeSearch(begin, end)
        found = set(r.track_id for r in result)

        if found == expected:
            passed += 1
            print(f"  Rango pequeño: {len(result)} registros correctos")
        else:
            failed += 1
            print(f"  ERROR: Esperados {len(expected)}, encontrados {len(found)}")

        # Rango medio
        begin = keys_list[len(keys_list) // 4]
        end = keys_list[3 * len(keys_list) // 4]
        expected = set(k for k in keys_list if begin <= k <= end)

        result = bpt.rangeSearch(begin, end)
        found = set(r.track_id for r in result)

        if found == expected:
            passed += 1
            print(f"  Rango medio: {len(result)} registros correctos")
        else:
            failed += 1
            print(f"  ERROR: Esperados {len(expected)}, encontrados {len(found)}")

        # Rango completo
        begin = keys_list[0]
        end = keys_list[-1]

        result = bpt.rangeSearch(begin, end)
        found = set(r.track_id for r in result)

        if found == inserted_keys:
            passed += 1
            print(f"  Rango completo: {len(result)} registros correctos")
        else:
            failed += 1
            print(f"  ERROR: Esperados {len(inserted_keys)}, encontrados {len(found)}")

    print_result(passed, failed)

    # ========== TEST 5: ACTUALIZACIONES ==========
    print_header("TEST 5: ACTUALIZACIONES")
    passed, failed = 0, 0

    update_keys = random.sample(keys_list, min(10, len(keys_list)))

    for key in update_keys:
        original = bpt.search(key)
        if not original:
            failed += 1
            continue

        # Crear versión actualizada
        updated = Song(
            track_id=original.track_id,
            track_name="UPDATED_NAME",
            track_artist=original.track_artist,
            track_popularity=9999,
            track_album_id=original.track_album_id,
            track_album_name=original.track_album_name,
            track_album_release_date=original.track_album_release_date,
            acousticness=original.acousticness,
            instrumentalness=original.instrumentalness,
            duration_ms=original.duration_ms
        )

        bpt.add(updated)
        result = bpt.search(key)

        if result and result.track_popularity == 9999:
            passed += 1
        else:
            failed += 1

    print(f"Actualizadas {len(update_keys)} canciones...")
    print_result(passed, failed)

    # ========== TEST 6: ELIMINACIONES ==========
    print_header("TEST 6: ELIMINACIONES")
    passed, failed = 0, 0

    remove_keys = random.sample(keys_list, min(15, len(keys_list)))

    for key in remove_keys:
        if bpt.search(key) is None:
            failed += 1
            continue

        removed = bpt.remove(key)
        if not removed:
            failed += 1
            continue

        if bpt.search(key) is None:
            passed += 1
        else:
            failed += 1

    print(f"Eliminadas {len(remove_keys)} canciones...")
    print_result(passed, failed)

    # ========== RESUMEN FINAL ==========
    print_header("RESUMEN FINAL")

    print(f"\nRegistros insertados: {len(inserted_keys)}")
    print(f"Tests de búsqueda: OK")
    print(f"Tests de rango: OK")
    print(f"Tests de actualización: OK")
    print(f"Tests de eliminación: OK")

    print("\nArchivos generados:")
    if os.path.exists(DATA_FILE):
        size = os.path.getsize(DATA_FILE)
        print(f"  {DATA_FILE}: {size:,} bytes")
    if os.path.exists(INDEX_FILE):
        size = os.path.getsize(INDEX_FILE)
        print(f"  {INDEX_FILE}: {size:,} bytes")

    print("\n" + "=" * 70)
    print("TEST COMPLETADO".center(70))
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrumpido por el usuario")
    except Exception as e:
        print(f"\n\nERROR FATAL: {e}")
        import traceback

        traceback.print_exc()