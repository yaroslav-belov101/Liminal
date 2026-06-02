import aiosqlite
import os
from datetime import datetime
from typing import List, Optional


# Путь к файлу базы данных
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "liminal.db")


async def init_db():
    """Инициализация базы данных: создание таблиц и оптимизация."""
    async with aiosqlite.connect(DB_PATH) as db:
        # 🔥 ОПТИМИЗАЦИИ ДЛЯ СКОРОСТИ
        
        # WAL-режим: позволяет читать во время записи (ускоряет в 2-3 раза)
        await db.execute("PRAGMA journal_mode=WAL")
        
        # Меньше проверок диска (быстрее запись, чуть меньше надёжности)
        await db.execute("PRAGMA synchronous=NORMAL")
        
        # Кэш в памяти (8 МБ) — меньше обращений к диску
        await db.execute("PRAGMA cache_size=-8000")
        
        # Храним временные файлы в памяти (быстрее сортировок)
        await db.execute("PRAGMA temp_store=MEMORY")
        
        # Включаем поддержку внешних ключей
        await db.execute("PRAGMA foreign_keys=ON")
        
        # --- Создание таблиц ---
        
        # Таблица пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица плейлистов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица треков в плейлистах
        await db.execute("""
            CREATE TABLE IF NOT EXISTS playlist_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                deezer_id TEXT,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                album TEXT,
                cover_url TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (playlist_id) REFERENCES playlists(id)
            )
        """)
        
        # 🔥 ИНДЕКСЫ ДЛЯ УСКОРЕНИЯ ПОИСКА
        
        # Ускоряет поиск плейлистов по пользователю
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_playlist_user 
            ON playlists(user_id)
        """)
        
        # Ускоряет получение треков плейлиста
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_track_playlist 
            ON playlist_tracks(playlist_id)
        """)
        
        # Ускоряет проверку дубликатов треков
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_track_deezer 
            ON playlist_tracks(playlist_id, deezer_id)
        """)
        
        await db.commit()
    
    print("✅ База данных инициализирована (WAL-режим + индексы)")


# --- Функции для работы с пользователями ---

async def create_user(user_id: int, username: str):
    """Создать пользователя или обновить username."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
        """, (user_id, username))
        await db.commit()


# --- Функции для работы с плейлистами ---

async def create_playlist(user_id: int, name: str) -> int:
    """Создать новый плейлист. Возвращает ID созданного плейлиста."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO playlists (user_id, name) 
            VALUES (?, ?)
        """, (user_id, name))
        await db.commit()
        return cursor.lastrowid


async def get_user_playlists(user_id: int) -> List[dict]:
    """Получить все плейлисты пользователя с количеством треков."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        cursor = await db.execute("""
            SELECT 
                p.id, 
                p.name, 
                p.created_at,
                COUNT(pt.id) as track_count
            FROM playlists p
            LEFT JOIN playlist_tracks pt ON p.id = pt.playlist_id
            WHERE p.user_id = ?
            GROUP BY p.id
            ORDER BY p.created_at DESC
        """, (user_id,))
        
        playlists = []
        async for row in cursor:
            playlists.append({
                'id': row['id'],
                'name': row['name'],
                'created_at': row['created_at'],
                'track_count': row['track_count']
            })
        
        return playlists


async def delete_playlist(playlist_id: int, user_id: int) -> bool:
    """Удалить плейлист (и все треки в нём). Возвращает True если удалено."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Сначала удаляем все треки из плейлиста
        await db.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))
        
        # Затем удаляем сам плейлист
        cursor = await db.execute("""
            DELETE FROM playlists 
            WHERE id = ? AND user_id = ?
        """, (playlist_id, user_id))
        await db.commit()
        
        return cursor.rowcount > 0


async def rename_playlist(playlist_id: int, user_id: int, new_name: str) -> bool:
    """Переименовать плейлист. Возвращает True если успешно."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            UPDATE playlists 
            SET name = ? 
            WHERE id = ? AND user_id = ?
        """, (new_name, playlist_id, user_id))
        await db.commit()
        return cursor.rowcount > 0


# --- Функции для работы с треками в плейлистах ---

async def add_track_to_playlist(
    playlist_id: int, 
    user_id: int,
    deezer_id: str,
    title: str, 
    artist: str, 
    album: str = "",
    cover_url: str = ""
) -> bool:
    """Добавить трек в плейлист. Возвращает True если добавлено."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем, что плейлист принадлежит пользователю
        cursor = await db.execute("""
            SELECT id FROM playlists 
            WHERE id = ? AND user_id = ?
        """, (playlist_id, user_id))
        
        if not await cursor.fetchone():
            return False
        
        # Проверяем, нет ли уже этого трека в плейлисте (используем индекс!)
        cursor = await db.execute("""
            SELECT id FROM playlist_tracks 
            WHERE playlist_id = ? AND deezer_id = ?
        """, (playlist_id, deezer_id))
        
        if await cursor.fetchone():
            return False  # Трек уже есть
        
        # Добавляем трек
        await db.execute("""
            INSERT INTO playlist_tracks (playlist_id, deezer_id, title, artist, album, cover_url)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (playlist_id, deezer_id, title, artist, album, cover_url))
        await db.commit()
        return True


async def get_playlist_tracks(playlist_id: int, user_id: int) -> List[dict]:
    """Получить все треки плейлиста (использует индекс)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Проверяем, что плейлист принадлежит пользователю
        cursor = await db.execute("""
            SELECT id FROM playlists 
            WHERE id = ? AND user_id = ?
        """, (playlist_id, user_id))
        
        if not await cursor.fetchone():
            return []
        
        # Получаем треки (сортируем по дате добавления)
        cursor = await db.execute("""
            SELECT id, deezer_id, title, artist, album, cover_url, added_at
            FROM playlist_tracks
            WHERE playlist_id = ?
            ORDER BY added_at ASC
        """, (playlist_id,))
        
        tracks = []
        async for row in cursor:
            tracks.append(dict(row))
        
        return tracks


async def remove_track_from_playlist(track_id: int, playlist_id: int, user_id: int) -> bool:
    """Удалить трек из плейлиста. Возвращает True если удалено."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем, что плейлист принадлежит пользователю
        cursor = await db.execute("""
            SELECT id FROM playlists 
            WHERE id = ? AND user_id = ?
        """, (playlist_id, user_id))
        
        if not await cursor.fetchone():
            return False
        
        # Удаляем трек
        cursor = await db.execute("""
            DELETE FROM playlist_tracks 
            WHERE id = ? AND playlist_id = ?
        """, (track_id, playlist_id))
        await db.commit()
        return cursor.rowcount > 0


async def get_playlist_info(playlist_id: int, user_id: int) -> Optional[dict]:
    """Получить информацию о плейлисте."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        cursor = await db.execute("""
            SELECT 
                p.id, 
                p.name, 
                p.created_at,
                COUNT(pt.id) as track_count
            FROM playlists p
            LEFT JOIN playlist_tracks pt ON p.id = pt.playlist_id
            WHERE p.id = ? AND p.user_id = ?
            GROUP BY p.id
        """, (playlist_id, user_id))
        
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None


async def track_exists_in_playlist(playlist_id: int, deezer_id: str) -> bool:
    """Быстрая проверка наличия трека в плейлисте (использует индекс)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT id FROM playlist_tracks 
            WHERE playlist_id = ? AND deezer_id = ?
        """, (playlist_id, deezer_id))
        
        return await cursor.fetchone() is not None