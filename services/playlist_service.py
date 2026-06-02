import os
import tempfile
import zipfile
import hashlib
from yt_dlp import YoutubeDL


def extract_playlist_info(url: str) -> dict | None:
    if 'spotify.com' in url:
        return extract_spotify_playlist(url)
    
    ydl_opts = {
        'extract_flat': 'in_playlist', 
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return None
            
            entries = info.get('entries', [])
            tracks = []
            
            for entry in entries:
                if entry:
                    tracks.append({
                        'title': entry.get('title', 'Неизвестно'),
                        'artist': entry.get('uploader', entry.get('channel', 'Неизвестно')),
                        'url': entry.get('url', entry.get('webpage_url', '')),
                        'duration': entry.get('duration', 0)
                    })
            
            total_duration = sum(t['duration'] for t in tracks if t['duration'])
            
            return {
                'title': info.get('title', 'Без названия'),
                'uploader': info.get('uploader', info.get('channel', 'Неизвестно')),
                'track_count': len(tracks),
                'total_duration': total_duration,
                'tracks': tracks,
                'url': url,
                'source': 'youtube'
            }
    except Exception as e:
        print(f"Ошибка извлечения плейлиста: {e}")
        return None


def extract_spotify_playlist(url: str) -> dict | None:
    ydl_opts = {
        'extract_flat': 'in_playlist',
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'ignoreerrors': True,
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return None
            
            entries = info.get('entries', [])
            tracks = []
            
            for entry in entries:
                if entry:
                    artist = entry.get('uploader', entry.get('channel', 'Неизвестно'))
                    title = entry.get('title', 'Неизвестно')
                    
                    if ' - ' in title and artist == 'Неизвестно':
                        parts = title.split(' - ', 1)
                        artist = parts[0].strip()
                        title = parts[1].strip()
                    
                    tracks.append({
                        'title': title,
                        'artist': artist,
                        'url': entry.get('url', ''),
                        'duration': entry.get('duration', 0)
                    })
            
            total_duration = sum(t['duration'] for t in tracks if t['duration'])
            
            return {
                'title': info.get('title', 'Spotify Playlist'),
                'uploader': info.get('uploader', 'Spotify'),
                'track_count': len(tracks),
                'total_duration': total_duration,
                'tracks': tracks,
                'url': url,
                'source': 'spotify' 
            }
    except Exception as e:
        print(f"Ошибка извлечения Spotify плейлиста: {e}")
        return None


def download_playlist_tracks(playlist_info: dict, progress_callback=None) -> list[str]:
    tracks = playlist_info['tracks']
    downloaded_files = []
    
    playlist_hash = hashlib.md5(playlist_info['url'].encode()).hexdigest()
    playlist_dir = os.path.join(tempfile.gettempdir(), f"liminal_playlist_{playlist_hash}")
    os.makedirs(playlist_dir, exist_ok=True)
    
    for i, track in enumerate(tracks):
        if progress_callback:
            progress_callback(i + 1, len(tracks))
        
        query = f"{track['artist']} - {track['title']}"
        out_template = os.path.join(playlist_dir, f"{i+1:02d} - %(title)s.%(ext)s")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch1',
            'outtmpl': out_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
        }
        
        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(f"ytsearch1:{query}", download=True)
                
                for file in os.listdir(playlist_dir):
                    if file.endswith('.mp3') and query[:20] in file:
                        file_path = os.path.join(playlist_dir, file)
                        if file_path not in downloaded_files:
                            downloaded_files.append(file_path)
                            break
        except Exception as e:
            print(f"Ошибка скачивания трека {i+1} ({track['artist']} - {track['title']}): {e}")
            continue
    
    return downloaded_files


def create_zip_archive(file_paths: list[str], archive_name: str) -> str | None:
    if not file_paths:
        return None
    
    archive_path = os.path.join(tempfile.gettempdir(), f"{archive_name}.zip")
    
    try:
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in file_paths:
                if os.path.exists(file_path):
                    arcname = os.path.basename(file_path)
                    zipf.write(file_path, arcname)
        
        return archive_path
    except Exception as e:
        print(f"Ошибка создания архива: {e}")
        return None