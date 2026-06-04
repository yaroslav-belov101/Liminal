import aiosqlite
import os
import json
from typing import List, Optional, Dict, Any

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "liminal.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA cache_size=-8000")
        await db.execute("PRAGMA temp_store=MEMORY")
        await db.execute("PRAGMA foreign_keys=ON")
        
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        await db.execute("""
        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)
        
        await db.execute("""
        CREATE TABLE IF NOT EXISTS playlist_tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER NOT NULL,
            deezer_id TEXT,
            title TEXT NOT NULL,
            artist TEXT NOT NULL,
            album TEXT,
            cover_url TEXT,
            file_id TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (playlist_id) REFERENCES playlists(id)
        )
        """)
        
        await db.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            genre_weights TEXT DEFAULT '{}',
            mood_weights TEXT DEFAULT '{}',
            lang_weights TEXT DEFAULT '{}',
            liked_artists TEXT DEFAULT '[]',
            disliked_artists TEXT DEFAULT '[]',
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)
        
        try:
            await db.execute("ALTER TABLE playlist_tracks ADD COLUMN file_id TEXT")
        except aiosqlite.OperationalError:
            pass
            
        await db.execute("CREATE INDEX IF NOT EXISTS idx_playlist_user ON playlists(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_track_playlist ON playlist_tracks(playlist_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_track_deezer ON playlist_tracks(playlist_id, deezer_id)")
        await db.commit()

async def create_user(user_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO users (user_id, username) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
        """, (user_id, username))
        
        await db.execute("""
        INSERT OR IGNORE INTO user_preferences (user_id) VALUES (?)
        """, (user_id,))
        await db.commit()

async def get_user_preferences(user_id: int) -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            return {"genre_weights": {}, "mood_weights": {}, "lang_weights": {}, "liked_artists": [], "disliked_artists": []}
        return {
            "genre_weights": json.loads(row["genre_weights"]),
            "mood_weights": json.loads(row["mood_weights"]),
            "lang_weights": json.loads(row["lang_weights"]),
            "liked_artists": json.loads(row["liked_artists"]),
            "disliked_artists": json.loads(row["disliked_artists"])
        }

async def update_user_preference(user_id: int, category: str, item: str, delta: float):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT genre_weights, mood_weights, lang_weights FROM user_preferences WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            return
            
        weights = json.loads(row[f"{category}_weights"])
        weights[item] = weights.get(item, 1.0) + delta
        weights[item] = max(0.1, weights[item])
        
        await db.execute(f"UPDATE user_preferences SET {category}_weights = ? WHERE user_id = ?", (json.dumps(weights), user_id))
        await db.commit()

async def add_to_user_list(user_id: int, list_name: str, item: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(f"SELECT {list_name} FROM user_preferences WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            return
        items = json.loads(row[list_name])
        if item not in items:
            items.append(item)
            await db.execute(f"UPDATE user_preferences SET {list_name} = ? WHERE user_id = ?", (json.dumps(items), user_id))
            await db.commit()

async def reset_user_preferences(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        UPDATE user_preferences SET 
        genre_weights = '{}', mood_weights = '{}', lang_weights = '{}', 
        liked_artists = '[]', disliked_artists = '[]' 
        WHERE user_id = ?
        """, (user_id,))
        await db.commit()

async def create_playlist(user_id: int, name: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("INSERT INTO playlists (user_id, name) VALUES (?, ?)", (user_id, name))
        await db.commit()
        return cursor.lastrowid

async def get_user_playlists(user_id: int) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
        SELECT p.id, p.name, p.created_at, COUNT(pt.id) as track_count
        FROM playlists p LEFT JOIN playlist_tracks pt ON p.id = pt.playlist_id
        WHERE p.user_id = ? GROUP BY p.id ORDER BY p.created_at DESC
        """, (user_id,))
        return [dict(row) async for row in cursor]

async def add_track_to_playlist(playlist_id: int, user_id: int, deezer_id: str, title: str, artist: str, album: str = "", cover_url: str = "", file_id: str = None) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id FROM playlists WHERE id = ? AND user_id = ?", (playlist_id, user_id))
        if not await cursor.fetchone():
            return False
        cursor = await db.execute("SELECT id FROM playlist_tracks WHERE playlist_id = ? AND deezer_id = ?", (playlist_id, deezer_id))
        if await cursor.fetchone():
            return False
        await db.execute("""
        INSERT INTO playlist_tracks (playlist_id, deezer_id, title, artist, album, cover_url, file_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (playlist_id, deezer_id, title, artist, album, cover_url, file_id))
        await db.commit()
        return True

async def update_track_file_id(track_id: int, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE playlist_tracks SET file_id = ? WHERE id = ?", (file_id, track_id))
        await db.commit()

async def get_playlist_tracks(playlist_id: int, user_id: int) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id FROM playlists WHERE id = ? AND user_id = ?", (playlist_id, user_id))
        if not await cursor.fetchone():
            return []
        cursor = await db.execute("""
        SELECT id, deezer_id, title, artist, album, cover_url, file_id, added_at
        FROM playlist_tracks WHERE playlist_id = ? ORDER BY added_at ASC
        """, (playlist_id,))
        return [dict(row) async for row in cursor]

async def delete_playlist(playlist_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))
        cursor = await db.execute("DELETE FROM playlists WHERE id = ? AND user_id = ?", (playlist_id, user_id))
        await db.commit()
        return cursor.rowcount > 0

async def rename_playlist(playlist_id: int, user_id: int, new_name: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("UPDATE playlists SET name = ? WHERE id = ? AND user_id = ?", (new_name, playlist_id, user_id))
        await db.commit()
        return cursor.rowcount > 0

async def get_playlist_info(playlist_id: int, user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
        SELECT p.id, p.name, p.created_at, COUNT(pt.id) as track_count
        FROM playlists p LEFT JOIN playlist_tracks pt ON p.id = pt.playlist_id
        WHERE p.id = ? AND p.user_id = ? GROUP BY p.id
        """, (playlist_id, user_id))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def track_exists_in_playlist(playlist_id: int, deezer_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id FROM playlist_tracks WHERE playlist_id = ? AND deezer_id = ?", (playlist_id, deezer_id))
        return await cursor.fetchone() is not None

async def remove_track_from_playlist(track_id: int, playlist_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id FROM playlists WHERE id = ? AND user_id = ?", (playlist_id, user_id))
        if not await cursor.fetchone():
            return False
        cursor = await db.execute("DELETE FROM playlist_tracks WHERE id = ? AND playlist_id = ?", (track_id, playlist_id))
        await db.commit()
        return cursor.rowcount > 0