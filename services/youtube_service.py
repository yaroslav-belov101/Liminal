import asyncio
import os
import tempfile
import hashlib
from yt_dlp import YoutubeDL
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
import requests

download_cache = {}


def download_track(title: str, artist: str, cover_url: str | None = None) -> dict | None:

    query = f"{artist} - {title}"
    query_hash = hashlib.md5(query.encode()).hexdigest()
    
    if query_hash in download_cache:
        cached_path = download_cache[query_hash]
        if os.path.exists(cached_path):
            print(f"✅ Кэш: трек '{query}' уже скачан, отдаём мгновенно")
            return {
                'file_path': cached_path,
                'title': title,
                'artist': artist,
                'cover_url': cover_url
            }
    
    out_file_template = os.path.join(tempfile.gettempdir(), f"liminal_{query_hash}.%(ext)s")
    final_mp3_path = out_file_template.replace('%(ext)s', 'mp3')

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch1',
        'outtmpl': out_file_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            
            if not info or 'entries' not in info or not info['entries']:
                return None
            
            if not os.path.exists(final_mp3_path):
                return None
            
            download_cache[query_hash] = final_mp3_path
            print(f"💾 Сохранено в кэш: {final_mp3_path}")
            
            return {
                'file_path': final_mp3_path,
                'title': title,
                'artist': artist,
                'cover_url': cover_url
            }
    except Exception as e:
        print(f"Ошибка скачивания: {e}")
        return None


def embed_cover_and_tags(file_path: str, title: str, artist: str, cover_url: str | None, album: str = "") -> bool:
    if not os.path.exists(file_path):
        return False
    
    try:
        cover_bytes = None
        if cover_url:
            response = requests.get(cover_url, timeout=10)
            if response.status_code == 200:
                cover_bytes = response.content
        
        audio = MP3(file_path)
        
        if audio.tags is None:
            audio.add_tags()
        
        audio.tags.add(TIT2(encoding=3, text=title))
        audio.tags.add(TPE1(encoding=3, text=artist))
        audio.tags.add(TALB(encoding=3, text=album))
        
        if cover_bytes:
            audio.tags.add(APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,
                desc='Cover',
                data=cover_bytes
            ))
        
        audio.save()
        return True
    except Exception as e:
        print(f"Ошибка вшивания тегов: {e}")
        return False