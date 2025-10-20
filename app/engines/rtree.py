import csv
from rtree import index
import math

CSV_FILE = 'app/data/datasets/AB_NYC_2019.csv'

class AirbnbRTreeManager:
    """
    Gestiona un índice R-Tree para el dataset de Airbnb.
    """
    def __init__(self):
        # Configura un índice para 2D (latitud, longitud)
        p = index.Property()
        p.dimension = 2
        self.idx = index.Index(properties=p)
        
        self.data_map = {}
        self.airbnb_id_to_rtree_id = {}
        self.next_rtree_id = 0

    def load_from_csv(self, file_path):
        print(f"Cargando datos desde '{file_path}'...")
        try:
            with open(file_path, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    try:
                        record = {
                            'id': row['id'],
                            'name': row['name'],
                            'neighbourhood': row['neighbourhood'],
                            'price': int(row['price']),
                            'coordinates': (float(row['latitude']), float(row['longitude']))
                        }
                        self.add(record) 
                    except (ValueError, KeyError):
                        pass
            print(f"¡Carga completa! Se indexaron {self.next_rtree_id} registros.")
        except FileNotFoundError:
            print(f"Error: El archivo '{file_path}' no fue encontrado.")
            exit()

    # --- OPERACIONES FUNDAMENTALES ---

    def add(self, record):
        """
        Agrega un nuevo registro al índice
        """
        airbnb_id = record['id']
        if airbnb_id in self.airbnb_id_to_rtree_id:
            print(f"Advertencia: El Airbnb con ID '{airbnb_id}' ya existe. No se agregó.")
            return False

        rtree_id = self.next_rtree_id
        coordinates = record['coordinates']
        bounding_box = (*coordinates, *coordinates)

        self.idx.insert(rtree_id, bounding_box)
        self.data_map[rtree_id] = record
        self.airbnb_id_to_rtree_id[airbnb_id] = rtree_id
        
        self.next_rtree_id += 1
        return True

    def search(self, airbnb_id):
        """
        Busca un registro específico por su ID de Airbnb
        """
        rtree_id = self.airbnb_id_to_rtree_id.get(airbnb_id)
        if rtree_id is not None:
            return self.data_map.get(rtree_id)
        return None

    def remove(self, airbnb_id):
        """
        Elimina un registro por su ID de Airbnb
        """
        rtree_id = self.airbnb_id_to_rtree_id.get(airbnb_id)
        if rtree_id is None:
            print(f"Error: No se encontró el Airbnb con ID '{airbnb_id}' para eliminar.")
            return False

        # Para eliminar del R-tree, necesitamos el ID interno y sus coordenadas
        record = self.data_map[rtree_id]
        coordinates = record['coordinates']
        bounding_box = (*coordinates, *coordinates)
        
        self.idx.delete(rtree_id, bounding_box)
        
        # Limpiamos los diccionarios
        del self.data_map[rtree_id]
        del self.airbnb_id_to_rtree_id[airbnb_id]
        
        print(f"Éxito: Se eliminó el Airbnb con ID '{airbnb_id}'.")
        return True

    # --- BÚSQUEDAS ESPACIALES ---

    def range_search(self, point, radius):
        """
        Busca en un radio en metros usando la distancia euclideana como aproximación.
        """
        lat, lon = point

        # --- Convertir el radio de metros a grados ---
        m_per_deg_lat = 111132  # Metros por grado de latitud 
        m_per_deg_lon = 111320 * math.cos(math.radians(lat)) # Metros por grado de longitud 
        
        # Usamos el promedio para tener un radio circular aproximado en grados
        avg_m_per_deg = (m_per_deg_lat + m_per_deg_lon) / 2
        radius_in_degrees = radius / avg_m_per_deg
        
        # --- Distancia euclideana ---
        
        # Creamos la caja de búsqueda con el radio en grados.
        search_box = (
            lat - radius_in_degrees, 
            lon - radius_in_degrees, 
            lat + radius_in_degrees, 
            lon + radius_in_degrees
        )
        
        candidate_ids = list(self.idx.intersection(search_box))
        
        results = []
        for rtree_id in candidate_ids:
            record = self.data_map[rtree_id]
            record_coords = record['coordinates']
            
            # Calculamos la distancia euclidiana
            distance_in_degrees = math.sqrt((record_coords[0] - point[0])**2 + (record_coords[1] - point[1])**2)
            
            # Comparamos la distancia con nuestro radio.
            if distance_in_degrees <= radius_in_degrees:
                results.append(record)
        
        return results

    def knn_search(self, point, k):
        # Lógica de búsqueda k-NN 
        nearest_ids = list(self.idx.nearest(point, k))
        return [self.data_map[rtree_id] for rtree_id in nearest_ids]


if __name__ == "__main__":
    
    print("Iniciando gestor de datos espaciales de Airbnb...")
    
    # 1. Cargar los datos iniciales
    airbnb_db = AirbnbRTreeManager()
    airbnb_db.load_from_csv(CSV_FILE)

    print("\n" + "="*50)
    print("EJECUTANDO PRUEBAS DE OPERACIONES FUNDAMENTALES")
    print("="*50)

    # --- Prueba A: Búsqueda ---
    print("\n[PRUEBA 1: Búsqueda de un Airbnb por ID]")
    id_a_buscar = '2539'
    resultado_busqueda = airbnb_db.search(id_a_buscar)
    if resultado_busqueda:
        print(f"Encontrado: {resultado_busqueda['name']}")
    else:
        print(f"No se encontró el Airbnb con ID {id_a_buscar}")
    
    # --- Prueba B: Inserción ---
    print("\n[PRUEBA 2: Insertar un nuevo Airbnb]")
    nuevo_airbnb = {
        'id': '99999999',
        'name': 'Apartment',
        'neighbourhood': 'Midtown',
        'price': 150,
        'coordinates': (40.7549, -73.9840) # Cerca de Times Square
    }
    airbnb_db.add(nuevo_airbnb)
    # Verificamos que se insertó buscándolo
    resultado_tras_add = airbnb_db.search('99999999')
    if resultado_tras_add:
        print(f"Verificación exitosa: Se encontró '{resultado_tras_add['name']}' después de agregarlo.")

    # --- Prueba C: Eliminación ---
    print("\n[PRUEBA 3: Eliminar el Airbnb insertado]")
    id_a_eliminar = '99999999'
    airbnb_db.remove(id_a_eliminar)
    # Verificamos que se eliminó intentando buscarlo de nuevo
    resultado_tras_remove = airbnb_db.search(id_a_eliminar)
    if not resultado_tras_remove:
        print(f"Verificación exitosa: El Airbnb con ID {id_a_eliminar} ya no existe.")

    # --- Prueba 4: Búsqueda por Radio (en metros) ---
    print("\n[PRUEBA 4: Búsqueda por Radio en Williamsburg]")
    williamsburg_center = (40.715, -73.955)
    radius = 550
    print(f"Buscando listings en un radio de {radius}° alrededor del centro de Williamsburg...")
    listings_in_williamsburg = airbnb_db.range_search(williamsburg_center, radius)
    print(f"Resultados encontrados: {len(listings_in_williamsburg)}")
    print("Mostrando los primeros 5:")
    for listing in listings_in_williamsburg[:5]:
        print(f"  - Nombre: {listing['name'][:40]:<43} | Precio: ${listing['price']}")

    # --- Prueba 5: Otro ejemplo de k-NN ---
    print("\n[PRUEBA 5: 5 Vecinos Más Cercanos a la Estatua de la Libertad]")
    statue_of_liberty_coords = (40.6892, -74.0445)
    k = 5
    print(f"Buscando los {k} listings más cercanos a la Estatua de la Libertad...")
    nearest_to_statue = airbnb_db.knn_search(statue_of_liberty_coords, k)
    print("Resultados encontrados:")
    for listing in nearest_to_statue:
        print(f"  - Nombre: {listing['name'][:40]:<43} | Barrio: {listing['neighbourhood']}")
        