import struct


class Restaurantes:
    FMT = "i20s12s"
    RECORD_SIZE = struct.calcsize(FMT)

    def __init__(self, id: int, nombre: str, fecharegistro: str):
        self.id = id
        self.nombre = nombre
        self.fecharegistro = fecharegistro

    def pack(self):
        nombre_bytes = (self.nombre or '').encode('utf-8')[:20].ljust(20, b'\x00')
        fecharegistro_bytes = (self.fecharegistro or '').encode('utf-8')[:12].ljust(12, b'\x00')
        record = struct.pack(
            self.FMT,
            self.id,
            nombre_bytes,
            fecharegistro_bytes,
        )
        return record

    @staticmethod
    def unpack(data):
        if not data or len(data) < Restaurantes.RECORD_SIZE:
            return None

        try:
            unpacked = struct.unpack(Restaurantes.FMT, data)
            _id, _nombre_raw, _fecharegistro_raw = unpacked
            id = _id
            nombre = _nombre_raw.decode('utf-8', errors='ignore').rstrip('\x00').strip()
            fecharegistro = _fecharegistro_raw.decode('utf-8', errors='ignore').rstrip('\x00').strip()

            return Restaurantes(
                id=id,
                nombre=nombre,
                fecharegistro=fecharegistro
            )
        except Exception:
            return None

    def __repr__(self):
        return f"Restaurantes(id={self.id!r}, nombre={self.nombre!r}, fecharegistro={self.fecharegistro!r}... )"
