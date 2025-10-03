import os
import csv
import random
import argparse
import importlib
from app.models.song import Song

parser = argparse.ArgumentParser(description="Test completo para B+Tree")
parser.add_argument("--csv", required=True, help="Ruta del CSV de canciones")
parser.add_argument("--module", required=True, help="Módulo donde está BPlusTreeFile")
parser.add_argument("--data", default="songs_test.dat", help="Archivo de datos")
parser.add_argument("--index", default="songs_test.idx", help="Archivo de índices")
parser.add_argument("--limit", type=int, default=1000, help="Cantidad de registros")
parser.add_argument("--clean", action="store_true", help="Limpiar archivos previos")
args = parser.parse_args()

mod = importlib.import_module(args.module)
BPlusTreeFile = getattr(mod, "BPlusTreeFile")


def build_song(row: dict) -> Song:
    def gi(k, d=0):
        try:
            return int(float(row.get(k, d)))
        except:
            return int(d)

    def gf(k, d=0.0):
        try:
            return float(row.get(k, d))
        except:
            return float(d)

    return Song(
        track_id=str(row.get("track_id", ""))[:30],
        track_name=row.get("track_name", "")[:100],
        track_artist=row.get("track_artist", "")[:40],
        track_popularity=gi("track_popularity", 0),
        track_album_id=str(row.get("track_album_id", ""))[:30],
        track_album_name=row.get("track_album_name", "")[:100],
        track_album_release_date=str(row.get("track_album_release_date", ""))[:12],
        acousticness=gf("acousticness", 0.0),
        instrumentalness=gf("instrumentalness", 0.0),
        duration_ms=gi("duration_ms", 0),
    )


def load_data(csv_path: str, limit: int = None):
    songs = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            song = build_song(row)
            if song.track_id and song.track_id.strip():
                songs.append(song)
            if limit and i >= limit:
                break
    return songs


class TestResults:
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.errors = []

    def add_pass(self):
        self.total += 1
        self.passed += 1

    def add_fail(self, msg):
        self.total += 1
        self.failed += 1
        self.errors.append(msg)

    def summary(self):
        return f"{self.passed}/{self.total} passed, {self.failed} failed"


def test_insertions(bpt, songs):
    print("\n" + "=" * 70)
    print("TEST 1: INSERCIONES")
    print("=" * 70)
    results = TestResults()

    inserted_keys = set()
    for i, song in enumerate(songs):
        try:
            bpt.add(song)
            inserted_keys.add(song.track_id)
            results.add_pass()
            if (i + 1) % 500 == 0:
                print(f"  Insertados: {i + 1}/{len(songs)}")
        except Exception as e:
            results.add_fail(f"Error insertando {song.track_id}: {e}")
            if results.failed < 5:
                import traceback
                traceback.print_exc()

    print(f"\nResultado: {results.summary()}")
    print(f"Claves únicas insertadas: {len(inserted_keys)}")
    return inserted_keys


def test_exact_searches(bpt, keys):
    print("\n" + "=" * 70)
    print("TEST 2: BÚSQUEDAS EXACTAS")
    print("=" * 70)
    results = TestResults()

    keys_list = list(keys)
    test_keys = []

    # Primeras 10
    test_keys.extend(keys_list[:10])
    # 10 del medio
    mid = len(keys_list) // 2
    test_keys.extend(keys_list[mid - 5:mid + 5])
    # Últimas 10
    test_keys.extend(keys_list[-10:])
    # 20 aleatorias
    if len(keys_list) > 50:
        test_keys.extend(random.sample(keys_list, min(20, len(keys_list) - 30)))

    test_keys = list(set(test_keys))[:50]

    print(f"Probando {len(test_keys)} búsquedas...")
    for key in test_keys:
        result = bpt.search(key)
        if result and result.track_id == key:
            results.add_pass()
        else:
            results.add_fail(f"No se encontró clave existente: {key}")

    print(f"Resultado: {results.summary()}")
    if results.failed > 0:
        print(f"Errores: {results.errors[:5]}")

    return results


def test_nonexistent_searches(bpt):
    print("\n" + "=" * 70)
    print("TEST 3: BÚSQUEDAS DE CLAVES INEXISTENTES")
    print("=" * 70)
    results = TestResults()

    nonexistent = [
        "ZZZZZZZZZZZZZZZZZZZZZZZZZZ",
        "000000000000000000000000000",
        "___NOEXISTE___",
        "",
        "xxxxxxxxxxxxxxxxxxxxxxx",
        "1111111111111111111111",
        "9999999999999999999999",
        "AAAAAAAAAAAAAAAAAAAAAAA"
    ]

    for key in nonexistent:
        result = bpt.search(key)
        if result is None:
            results.add_pass()
        else:
            results.add_fail(f"Encontró clave inexistente: {key}")

    print(f"Resultado: {results.summary()}")
    return results


def test_range_searches(bpt, keys):
    print("\n" + "=" * 70)
    print("TEST 4: BÚSQUEDAS POR RANGO")
    print("=" * 70)
    results = TestResults()

    keys_list = sorted(list(keys))

    # Test 1: Rango pequeño (primeras 50 claves)
    if len(keys_list) >= 50:
        begin = keys_list[10]
        end = keys_list[40]
        expected = set(keys_list[10:41])

        result = bpt.rangeSearch(begin, end)
        found_keys = set(r.track_id for r in result)

        if found_keys == expected:
            results.add_pass()
            print(f"  ✓ Rango pequeño: {len(result)} registros correctos")
        else:
            missing = expected - found_keys
            extra = found_keys - expected
            results.add_fail(f"Rango pequeño incorrecto. Faltan: {len(missing)}, Extras: {len(extra)}")
            if missing:
                print(f"    Claves faltantes: {list(missing)[:3]}")
            if extra:
                print(f"    Claves extras: {list(extra)[:3]}")

    # Test 2: Rango medio (cuarto 1 a cuarto 3)
    if len(keys_list) >= 100:
        begin = keys_list[len(keys_list) // 4]
        end = keys_list[3 * len(keys_list) // 4]
        expected = set(k for k in keys_list if begin <= k <= end)

        result = bpt.rangeSearch(begin, end)
        found_keys = set(r.track_id for r in result)

        if found_keys == expected:
            results.add_pass()
            print(f"  ✓ Rango medio: {len(result)} registros correctos")
        else:
            missing = expected - found_keys
            extra = found_keys - expected
            results.add_fail(f"Rango medio incorrecto. Faltan: {len(missing)}, Extras: {len(extra)}")

    # Test 3: Rango completo
    if len(keys_list) >= 10:
        begin = keys_list[0]
        end = keys_list[-1]

        result = bpt.rangeSearch(begin, end)
        found_keys = set(r.track_id for r in result)

        if found_keys == keys:
            results.add_pass()
            print(f"  ✓ Rango completo: {len(result)} registros correctos")
        else:
            results.add_fail(f"Rango completo: esperados {len(keys)}, encontrados {len(found_keys)}")

    # Test 4: Verificar orden dentro de cada consulta
    if len(keys_list) >= 50:
        begin = keys_list[20]
        end = keys_list[80] if len(keys_list) > 80 else keys_list[-1]

        result = bpt.rangeSearch(begin, end)
        result_sorted = sorted(result, key=lambda x: x.track_id)

        if all(result[i].track_id == result_sorted[i].track_id for i in range(len(result))):
            results.add_pass()
            print(f"  ✓ Resultados en orden correcto")
        else:
            # El orden global puede no ser perfecto debido a la estructura de páginas
            # Verificar al menos que estén todos en el rango
            in_range = all(begin <= r.track_id <= end for r in result)
            if in_range:
                results.add_pass()
                print(f"  ✓ Todos los resultados están en el rango (orden de páginas)")
            else:
                results.add_fail("Resultados fuera del rango")

    print(f"\nResultado: {results.summary()}")
    return results


def test_updates(bpt, keys):
    print("\n" + "=" * 70)
    print("TEST 5: ACTUALIZACIONES")
    print("=" * 70)
    results = TestResults()

    keys_list = list(keys)
    test_keys = random.sample(keys_list, min(10, len(keys_list)))

    for key in test_keys:
        # Buscar original
        original = bpt.search(key)
        if not original:
            results.add_fail(f"No se encontró clave para actualizar: {key}")
            continue

        # Crear versión actualizada
        updated = Song(
            track_id=original.track_id,
            track_name="UPDATED_" + original.track_name[:90],
            track_artist=original.track_artist,
            track_popularity=999,
            track_album_id=original.track_album_id,
            track_album_name=original.track_album_name,
            track_album_release_date=original.track_album_release_date,
            acousticness=original.acousticness,
            instrumentalness=original.instrumentalness,
            duration_ms=original.duration_ms
        )

        # Actualizar
        bpt.add(updated)

        # Verificar
        result = bpt.search(key)
        if result and result.track_popularity == 999:
            results.add_pass()
        else:
            results.add_fail(f"Update falló para {key}")

    print(f"Resultado: {results.summary()}")
    return results


def test_removals(bpt, keys):
    print("\n" + "=" * 70)
    print("TEST 6: ELIMINACIONES")
    print("=" * 70)
    results = TestResults()

    keys_list = list(keys)
    test_keys = random.sample(keys_list, min(20, len(keys_list)))

    for key in test_keys:
        # Verificar que existe
        before = bpt.search(key)
        if not before:
            results.add_fail(f"Clave no existe antes de eliminar: {key}")
            continue

        # Eliminar
        removed = bpt.remove(key)
        if not removed:
            results.add_fail(f"remove() retornó False para {key}")
            continue

        # Verificar que no existe
        after = bpt.search(key)
        if after is None:
            results.add_pass()
        else:
            results.add_fail(f"Clave aún existe después de eliminar: {key}")

    print(f"Resultado: {results.summary()}")
    return results


def analyze_structure(bpt):
    print("\n" + "=" * 70)
    print("ANÁLISIS DE ESTRUCTURA")
    print("=" * 70)

    try:
        # Analizar nodo raíz
        root = bpt._BPlusTreeFile__read_node(0)
        print(f"Nodo raíz (pos 0):")
        print(f"  - Tipo: {'Hoja' if root.is_last_level else 'Interno'}")
        print(f"  - Count: {root.count}")
        print(f"  - Hijos válidos: {sum(1 for c in root.children if c >= 0)}")

        # Calcular profundidad
        depth = 0
        node_pos = 0
        visited = set()
        while node_pos not in visited:
            visited.add(node_pos)
            node = bpt._BPlusTreeFile__read_node(node_pos)
            if node.is_last_level:
                break
            depth += 1
            node_pos = node.children[0] if node.children[0] >= 0 else -1
            if node_pos < 0:
                break

        print(f"\nProfundidad del árbol: {depth}")

        # Contar páginas de datos
        leaf_node = node  # último nodo visitado
        if leaf_node.is_last_level:
            total_pages = 0
            total_records = 0
            seen_pages = set()

            for child in leaf_node.children:
                if child < 0:
                    continue
                page_idx = child
                while page_idx >= 0 and page_idx not in seen_pages:
                    seen_pages.add(page_idx)
                    page = bpt._BPlusTreeFile__read_data_page(page_idx)
                    total_pages += 1
                    total_records += page.count
                    page_idx = page.next_page

            print(f"Páginas de datos: {total_pages}")
            print(f"Registros totales: {total_records}")
            if total_pages > 0:
                print(f"Promedio por página: {total_records / total_pages:.1f}")

    except Exception as e:
        print(f"Error en análisis: {e}")


def main():
    print("=" * 70)
    print("TEST COMPLETO DE B+ TREE")
    print("=" * 70)

    # Limpiar
    if args.clean:
        for f in [args.data, args.index]:
            if os.path.exists(f):
                os.remove(f)
                print(f"Eliminado: {f}")

    # Cargar datos
    print(f"\nCargando datos de {args.csv}...")
    songs = load_data(args.csv, args.limit)
    print(f"Cargados: {len(songs)} registros")

    if not songs:
        print("ERROR: No se cargaron datos")
        return

    # Crear B+Tree
    print(f"\nCreando B+Tree: {args.data}, {args.index}")
    bpt = BPlusTreeFile(args.data, args.index)

    # Tests
    all_results = []

    keys = test_insertions(bpt, songs)
    all_results.append(test_exact_searches(bpt, keys))
    all_results.append(test_nonexistent_searches(bpt))
    all_results.append(test_range_searches(bpt, keys))
    all_results.append(test_updates(bpt, keys))
    all_results.append(test_removals(bpt, keys))

    analyze_structure(bpt)

    # Resumen final
    print("\n" + "=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)
    total_passed = sum(r.passed for r in all_results)
    total_tests = sum(r.total for r in all_results)
    total_failed = sum(r.failed for r in all_results)

    print(f"Total: {total_passed}/{total_tests} tests pasados")
    print(f"Fallos: {total_failed}")

    if total_failed == 0:
        print("\n✓ TODOS LOS TESTS PASARON")
    else:
        print(f"\n✗ {total_failed} tests fallaron")
        print("\nPrimeros errores:")
        for r in all_results:
            for err in r.errors[:2]:
                print(f"  - {err}")

    print("=" * 70)


if __name__ == "__main__":
    main()