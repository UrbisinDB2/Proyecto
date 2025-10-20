import os
import time
import random
import pandas as pd
import matplotlib.pyplot as plt
import shutil

from app.data.records.song import Song
from app.engines.seqfile import SequentialFile
from app.engines.bplustree import BPlusTreeFile
from app.engines.extendiblehashing import ExtendibleHashingFile

CSV_FILE = 'app/data/datasets/spotify_songs.csv'
DATA_LIMIT = 32828              # Carga masiva inicial
SEARCH_SAMPLE_SIZE = 100        # Elementos a buscar
INSERTION_COUNT = 100           # Elementos nuevos a insertar
DELETION_COUNT = 100            # Elementos a eliminar
TEST_DIR = 'test_data'

# --- Funciones de Ayuda ---

def setup_environment():
    """Limpia y crea el directorio para los archivos de datos de prueba."""
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)
    print(f"Directorio de pruebas '{TEST_DIR}' creado/limpiado.")

def load_data(limit: int) -> list[Song]:
    """Carga datos desde el CSV, los limpia y los convierte en objetos Song."""
    print(f"Intentando cargar hasta {limit + 500} registros para asegurar suficientes datos...")
    df = pd.read_csv(CSV_FILE, nrows=limit + 500)

    df.dropna(subset=['track_id'], inplace=True)
    df.drop_duplicates(subset=['track_id'], inplace=True)

    df.fillna({
        'track_name': '', 'track_artist': '', 'track_album_id': '', 'track_album_name': '',
        'track_album_release_date': '1900-01-01'
    }, inplace=True)
    for col in ['track_popularity', 'acousticness', 'instrumentalness', 'duration_ms']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Tomamos solo el límite deseado DESPUÉS de limpiar
    df = df.head(limit)

    songs = [Song(
        track_id=str(row['track_id']), track_name=str(row['track_name']),
        track_artist=str(row['track_artist']), track_popularity=int(row['track_popularity']),
        track_album_id=str(row['track_album_id']), track_album_name=str(row['track_album_name']),
        track_album_release_date=str(row['track_album_release_date']),
        acousticness=float(row['acousticness']), instrumentalness=float(row['instrumentalness']),
        duration_ms=int(row['duration_ms'])
    ) for _, row in df.iterrows()]
    
    print(f"Se cargaron {len(songs)} registros únicos y limpios para las pruebas.")
    return songs

# --- Funciones de Ploteo (Una por cada gráfico) ---

def plot_bulk_load(results: dict, count: int):
    plt.figure(figsize=(10, 6))
    for tech, data in results.items():
        plt.plot(data['records'], data['time'], marker='o', linestyle='-', label=tech)
    plt.title('Gráfico 1: Rendimiento de Carga Inicial')
    plt.xlabel('Número de Registros Insertados'); plt.ylabel('Tiempo Acumulado (s)')
    plt.grid(True); plt.legend(); plt.tight_layout()
    plt.savefig('1_bulk_load_performance.png')
    print("\nGráfico '1_bulk_load_performance.png' generado.")
    plt.show()

def plot_search(results: dict, count: int):
    techs, times = list(results.keys()), list(results.values())
    plt.figure(figsize=(10, 6))
    bars = plt.bar(techs, times, color=['skyblue', 'lightgreen', 'salmon'])
    plt.title(f'Gráfico 2: Tiempo de Búsqueda ({count} elementos)')
    plt.xlabel('Técnica de Indexación'); plt.ylabel('Tiempo Total (s)')
    plt.grid(axis='y', linestyle='--')
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval, f'{yval:.4f} s', va='bottom', ha='center')
    plt.tight_layout()
    plt.savefig('2_search_performance.png')
    print("Gráfico '2_search_performance.png' generado.")
    plt.show()

def plot_average_time(results: dict, count: int, operation: str, chart_number: int):
    techs, times = list(results.keys()), list(results.values())
    if count == 0:
        print(f"No se realizaron operaciones de {operation}, omitiendo gráfico.")
        return
    avg_times = [t / count for t in times]
    filename = f'{chart_number}_average_{operation.lower()}_time.png'
    
    plt.figure(figsize=(10, 6))
    bars = plt.bar(techs, avg_times, color=['#ff9999','#66b3ff','#99ff99'])
    plt.title(f'Gráfico {chart_number}: Tiempo Promedio por {operation} ({count} elementos)')
    plt.xlabel('Técnica de Indexación'); plt.ylabel('Tiempo Promedio (s)')
    plt.grid(axis='y', linestyle='--')
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval, f'{yval:.6f} s', va='bottom', ha='center')
    plt.tight_layout()
    plt.savefig(filename)
    print(f"Gráfico '{filename}' generado.")
    plt.show()

# --- Funciones de Benchmarking ---

def get_structures():
    """Función helper para inicializar las estructuras."""
    return {
        'Sequential File': SequentialFile(main_path=f'{TEST_DIR}/seq.main', aux_path=f'{TEST_DIR}/seq.aux'),
        'B+ Tree': BPlusTreeFile(datafile=f'{TEST_DIR}/bpt.data', indexfile=f'{TEST_DIR}/bpt.index'),
        'Extendible Hashing': ExtendibleHashingFile(datafile=f'{TEST_DIR}/eh.data', dirfile=f'{TEST_DIR}/eh.dir')
    }

def benchmark_bulk_insertion(songs: list[Song]):
    results = {'Sequential File': {'records':[],'time':[]}, 'B+ Tree': {'records':[],'time':[]}, 'Extendible Hashing': {'records':[],'time':[]}}
    for name, struct in get_structures().items():
        print(f"\n--- Probando Carga Inicial: {name} ---")
        start_time = time.time()
        if hasattr(struct, 'bulk_load'):
            struct.bulk_load(songs)
            results[name]['records'].append(len(songs)); results[name]['time'].append(time.time() - start_time)
        else:
            for i, song in enumerate(songs):
                struct.add(song)
                if (i + 1) % 1000 == 0 or (i + 1) == len(songs):
                    results[name]['records'].append(i + 1); results[name]['time'].append(time.time() - start_time)
        print(f"Tiempo total: {results[name]['time'][-1]:.4f} segundos.")
    return results

def benchmark_operation(data, operation_name: str, is_song_obj=False):
    results = {}
    if not data:
        print(f"\nNo hay datos para la operación de {operation_name}. Omitiendo.")
        return {'Sequential File': 0, 'B+ Tree': 0, 'Extendible Hashing': 0}
        
    for name, struct in get_structures().items():
        print(f"\n--- Probando {operation_name}: {name} ---")
        op_func = getattr(struct, operation_name.lower())
        
        start_time = time.time()
        if is_song_obj:
            for item in data: op_func(item)
            count = len(data)
        else:
            count = sum(1 for key in data if op_func(key))
            
        total_time = time.time() - start_time
        results[name] = total_time
        print(f"Tiempo total: {total_time:.4f} s. ({count}/{len(data)} operaciones exitosas)")
    return results

# --- Ejecución Principal ---
if __name__ == "__main__":
    setup_environment()
    try:
        # Cargar datos suficientes para todas las pruebas
        total_needed = DATA_LIMIT + INSERTION_COUNT
        all_songs = load_data(limit=total_needed)
        
        # --- AJUSTE DINÁMICO DE TAMAÑOS DE PRUEBA ---
        total_loaded = len(all_songs)
        
        # Usamos los valores configurados o el máximo posible sin solapamiento
        actual_insertion_count = min(INSERTION_COUNT, total_loaded)
        initial_load_size = total_loaded - actual_insertion_count
        
        # Dividimos los datos para cada prueba
        initial_load_songs = all_songs[:initial_load_size]
        single_insertion_songs = all_songs[initial_load_size:]

        # Ajustamos los tamaños de búsqueda y eliminación para no exceder los datos de carga inicial
        actual_search_size = min(SEARCH_SAMPLE_SIZE, initial_load_size)
        actual_deletion_count = min(DELETION_COUNT, initial_load_size)

        print("\n--- Tamaños de prueba ajustados a los datos disponibles ---")
        print(f"Carga Inicial: {len(initial_load_songs)} registros")
        print(f"Búsquedas Aleatorias: {actual_search_size} registros")
        print(f"Inserciones Nuevas: {len(single_insertion_songs)} registros")
        print(f"Eliminaciones Aleatorias: {actual_deletion_count} registros")
        print("----------------------------------------------------------\n")
        
        # --- PRUEBA 1: CARGA INICIAL ---
        bulk_results = benchmark_bulk_insertion(initial_load_songs)
        plot_bulk_load(bulk_results, count=len(initial_load_songs))

        # --- PRUEBA 2: BÚSQUEDA ---
        search_keys = [s.track_id for s in random.sample(initial_load_songs, actual_search_size)]
        search_results = benchmark_operation(search_keys, "Search")
        plot_search(search_results, count=actual_search_size)

        # --- PRUEBA 3: INSERCIONES INDIVIDUALES ---
        insertion_results = benchmark_operation(single_insertion_songs, "Add", is_song_obj=True)
        plot_average_time(insertion_results, len(single_insertion_songs), "Inserción", chart_number=3)
        
        # --- PRUEBA 4: ELIMINACIÓN ---
        keys_to_delete = [s.track_id for s in random.sample(initial_load_songs, actual_deletion_count)]
        deletion_results = benchmark_operation(keys_to_delete, "Remove")
        plot_average_time(deletion_results, actual_deletion_count, "Eliminación", chart_number=4)

    finally:
        print("\n--- Limpiando archivos de prueba ---")
        if os.path.exists(TEST_DIR):
            shutil.rmtree(TEST_DIR)
            print(f"Directorio '{TEST_DIR}' eliminado. ¡Limpieza completada!")
