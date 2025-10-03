import os
import csv
import signal
import sys
from app.models.song import Song
from app.engines.bplustree import BPlusTreeFile


# Timeout handler
def timeout_handler(signum, frame):
    print("\n⚠️ TIMEOUT! El programa se colgó.")
    print("Probablemente hay un loop infinito en el split o inserción.")
    sys.exit(1)


def build_song(row: dict) -> Song:
    def gi(k, d=0):
        v = row.get(k, d)
        try:
            return int(v)
        except:
            try:
                return int(float(v))
            except:
                return int(d)

    def gf(k, d=0.0):
        v = row.get(k, d)
        try:
            return float(v)
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


def main():
    # Limpiar archivos
    for f in ["test.dat", "test.idx"]:
        if os.path.exists(f):
            os.remove(f)

    bpt = BPlusTreeFile("test.dat", "test.idx")

    csv_path = r".\data\datasets\clean_spotify_songs.csv"

    print("Insertando registros con debug...")

    # Configurar timeout de 5 segundos por inserción
    if hasattr(signal, 'SIGALRM'):
        signal.signal(signal.SIGALRM, timeout_handler)

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        n = 0

        for row in reader:
            song = build_song(row)
            if not song.track_id or not song.track_id.strip():
                continue

            print(f"\n[{n}] Insertando: {song.track_id[:20]}", end=" ")

            try:
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(5)  # 5 segundos timeout

                bpt.add(song)

                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)  # Cancelar timeout

                print("✓")

            except Exception as e:
                print(f"\n✗ ERROR: {e}")
                import traceback
                traceback.print_exc()
                break

            n += 1

            if n >= 500:  # Limitar a 500 para debug
                break

    print(f"\n✓ Completado: {n} registros insertados")

    # Verificar algunas búsquedas
    print("\nProbando búsquedas...")
    test_key = "008MceT31RotUANsKuzyOZ"
    result = bpt.search(test_key)
    print(f"search('{test_key}') -> {'Encontrado' if result else 'No encontrado'}")


if __name__ == "__main__":
    main()