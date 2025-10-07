import struct


class Song:
    FMT = "30s100s40si30s100s12sffi"
    RECORD_SIZE = struct.calcsize(FMT)

    def __init__(self, track_id: str, track_name: str, track_artist: str, track_popularity: int,
                 track_album_id: str, track_album_name: str, track_album_release_date: str,
                 acousticness: float, instrumentalness: float, duration_ms: int):
        self.track_id = track_id
        self.track_name = track_name
        self.track_artist = track_artist
        self.track_popularity = track_popularity
        self.track_album_id = track_album_id
        self.track_album_name = track_album_name
        self.track_album_release_date = track_album_release_date
        self.acousticness = acousticness
        self.instrumentalness = instrumentalness
        self.duration_ms = duration_ms

    def pack(self):
        track_id_bytes = self.track_id.encode('utf-8')[:30].ljust(30, b'\x00')
        track_name_bytes = self.track_name.encode('utf-8')[:100].ljust(100, b'\x00')
        track_artist_bytes = self.track_artist.encode('utf-8')[:40].ljust(40, b'\x00')
        track_album_id_bytes = self.track_album_id.encode('utf-8')[:30].ljust(30, b'\x00')
        track_album_name_bytes = self.track_album_name.encode('utf-8')[:100].ljust(100, b'\x00')
        track_album_release_date_bytes = self.track_album_release_date.encode('utf-8')[:12].ljust(12, b'\x00')

        record = struct.pack(
            self.FMT,
            track_id_bytes,
            track_name_bytes,
            track_artist_bytes,
            self.track_popularity,
            track_album_id_bytes,
            track_album_name_bytes,
            track_album_release_date_bytes,
            self.acousticness,
            self.instrumentalness,
            self.duration_ms
        )
        return record

    @staticmethod
    def unpack(data):
        if not data or len(data) < Song.RECORD_SIZE:
            return None

        try:
            unpacked = struct.unpack(Song.FMT, data)
            track_id, track_name, track_artist, track_popularity, track_album_id, \
                track_album_name, track_album_release_date, acousticness, instrumentalness, duration_ms = unpacked

            return Song(
                track_id=track_id.decode('utf-8', errors='ignore').rstrip('\x00').strip(),
                track_name=track_name.decode('utf-8', errors='ignore').rstrip('\x00').strip(),
                track_artist=track_artist.decode('utf-8', errors='ignore').rstrip('\x00').strip(),
                track_popularity=track_popularity,
                track_album_id=track_album_id.decode('utf-8', errors='ignore').rstrip('\x00').strip(),
                track_album_name=track_album_name.decode('utf-8', errors='ignore').rstrip('\x00').strip(),
                track_album_release_date=track_album_release_date.decode('utf-8', errors='ignore').rstrip(
                    '\x00').strip(),
                acousticness=acousticness,
                instrumentalness=instrumentalness,
                duration_ms=duration_ms
            )
        except Exception as e:
            # En caso de error, retornar None
            return None

    def __repr__(self):
        return f"Song(track_id='{self.track_id[:20]}...', name='{self.track_name[:30]}...')"