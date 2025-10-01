import struct

class Song:
    FMT = "30s100s40si30s100s12sffi"
    RECORD_SIZE = struct.calcsize(FMT)

    def __init__(self, track_id : str, track_name : str, track_artist : str, track_popularity : int, track_album_id : str,
                 track_album_name : str, track_album_release_date : str, acousticness : float, instrumentalness : float, duration_ms : int):
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

    def pask(self):
        record = struct.pack(self.FMT, self.track_id.encode(), self.track_name.encode(), self.track_artist.encode(), self.track_popularity,
                             self.track_album_id.encode(), self.track_album_name.encode(), self.track_album_release_date.encode(), self.acousticness,
                             self.instrumentalness, self.duration_ms)
        return record

    @staticmethod
    def unpack(data):
        if not data:
            return None
        track_id, track_name, track_artist, track_popularity, track_album_id, track_album_name, track_album_release_date, acousticness, instrumentalness, duration_ms = struct.unpack(Song.FMT, data)
        return Song(
            track_id=track_id.decode().strip(),
            track_name=track_name.decode().strip(),
            track_artist=track_artist.decode().strip(),
            track_popularity=track_popularity,
            track_album_id=track_album_id.decode().strip(),
            track_album_name=track_album_name.decode().strip(),
            track_album_release_date=track_album_release_date.decode().strip(),
            acousticness=acousticness,
            instrumentalness=instrumentalness,
            duration_ms=duration_ms
        )