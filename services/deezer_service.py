import requests
import asyncio


def search_track_deezer(query: str):

    try:
        url = f"https://api.deezer.com/search/track?q={query}&limit=1&output=json"
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('data') and len(data['data']) > 0:
            track = data['data'][0]
            
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