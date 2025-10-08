import pandas as pd

df = pd.read_csv("spotify_songs.csv")

print(df.head())
print(df.columns)

df = df.drop(columns=["playlist_name", "playlist_id", "playlist_genre", "playlist_subgenre", "key", "mode", "speechiness", "liveness", "valence", "tempo", "danceability", "energy", "loudness"])
print(df.head())
print(df.columns)

df = df.dropna()

print(df.isnull().sum())

if df.isnull().values.any():
    print("\nExisten valores nulos en el dataset")
else:
    print("\nNo hay valores nulos")

df.to_csv("spotify_songs.csv", index=False)