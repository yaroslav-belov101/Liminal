import requests
import random

ARTIST_SEEDS = {
    "russian_rock": ["русский рок", "русский инди", "альтернативная музыка"],
    "russian_pop": ["русская поп музыка", "российская эстрада", "русский поп"],
    "russian_hiphop": ["русский рэп", "русский хип-хоп", "андеграунд рэп"],
    "russian_melancholy": ["русская лирика", "грустная русская музыка", "русский шансон"],
    "russian_energetic": ["русский драйв", "русский панк", "русский метал"],
    "russian_night": ["русская ночь", "русский пост-панк", "русский эмбиент"],
    "russian_focus": ["русский инструментал", "саундтреки русские"],
    "russian_romance": ["русские баллады", "русская романтика"]
}

def get_dynamic_artist_and_track(mood_kw: str, genre_kw: str, lang: str, exclude_ids: list, limit: int = 10):
    if exclude_ids is None:
        exclude_ids = []
        
    try:
        seed_category = f"{lang}_{mood_kw}" if mood_kw else f"{lang}_{genre_kw}"
        seeds = ARTIST_SEEDS.get(seed_category, ARTIST_SEEDS.get(f"{lang}_rock", ["русская музыка"]))
        seed_query = random.choice(seeds)
        
        artist_url = f"https://api.deezer.com/search/artist?q={seed_query}&limit=20&output=json"
        artist_response = requests.get(artist_url, timeout=10)
        artist_data = artist_response.json()
        
        if not artist_data.get('data') or len(artist_data['data']) == 0:
            return None
            
        random_artist = random.choice(artist_data['data'])
        artist_name = random_artist['name']
        
        track_url = f"https://api.deezer.com/search/track?q=artist:\"{artist_name}\"&limit={limit}&output=json"
        track_response = requests.get(track_url, timeout=10)
        track_data = track_response.json()
        
        if track_data.get('data') and len(track_data['data']) > 0:
            valid_tracks = [
                track for track in track_data['data'] 
                if str(track['id']) not in exclude_ids
            ]
            
            if not valid_tracks:
                return None
                
            track = random.choice(valid_tracks)
            cover_url = track['album'].get('cover_xl') or track['album'].get('cover_big')
            
            return {
                "title": track['title'],
                "artist": track['artist']['name'],
                "album": track['album']['title'],
                "cover_url": cover_url,
                "deezer_id": str(track['id']),
                "preview_url": track.get('preview')
            }
    except Exception as e:
        print(f"Ошибка динамического поиска артистов: {e}")
        return None

def search_track_deezer(query: str, genre: str = None, exclude_ids: list = None, limit: int = 10, lang: str = None):
    if exclude_ids is None:
        exclude_ids = []
    
    try:
        search_query = query.strip()
        
        if lang == "russian":
            mood_key = next((k for k in ["melancholy", "cheerful", "energetic", "night", "focus", "romance"] if k in query.lower()), None)
            genre_key = genre.lower() if genre else "rock"
            
            dynamic_result = get_dynamic_artist_and_track(
                mood_kw=mood_key, 
                genre_kw=genre_key, 
                lang="russian", 
                exclude_ids=exclude_ids, 
                limit=limit
            )
            if dynamic_result:
                return dynamic_result
            
            search_query = "русская музыка"
        elif genre:
            search_query = f'genre:"{genre}" {search_query}'
            
        url = f"https://api.deezer.com/search/track?q={search_query}&limit={limit}&output=json"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('data') and len(data['data']) > 0:
            valid_tracks = [track for track in data['data'] if str(track['id']) not in exclude_ids]
            if not valid_tracks:
                return None
                
            track = random.choice(valid_tracks)
            cover_url = track['album'].get('cover_xl') or track['album'].get('cover_big')
            
            return {
                "title": track['title'],
                "artist": track['artist']['name'],
                "album": track['album']['title'],
                "cover_url": cover_url,
                "deezer_id": str(track['id']),
                "preview_url": track.get('preview')
            }
    except Exception as e:
        print(f"Ошибка Deezer API: {e}")
        return None

def get_radio_tracks_by_genre(genre_name: str, exclude_ids: list = None):
    if exclude_ids is None:
        exclude_ids = []
        
    try:
        radios = requests.get("https://api.deezer.com/radio", timeout=10).json()
        for radio in radios.get('data', []):
            if genre_name.lower() in radio['title'].lower():
                tracks_resp = requests.get(f"https://api.deezer.com/radio/{radio['id']}/tracks?limit=10", timeout=10).json()
                if tracks_resp.get('data'):
                    valid_tracks = [track for track in tracks_resp['data'] if str(track['id']) not in exclude_ids]
                    if valid_tracks:
                        track = random.choice(valid_tracks)
                        cover_url = track['album'].get('cover_xl') or track['album'].get('cover_big')
                        return {
                            "title": track['title'],
                            "artist": track['artist']['name'],
                            "album": track['album']['title'],
                            "cover_url": cover_url,
                            "deezer_id": str(track['id']),
                            "preview_url": track.get('preview')
                        }
        return None
    except Exception as e:
        print(f"Ошибка Deezer Radio API: {e}")
        return None