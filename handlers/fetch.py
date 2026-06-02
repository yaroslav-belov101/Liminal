import asyncio
import os
import tempfile
import hashlib
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from yt_dlp import YoutubeDL
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
import requests

from services.playlist_service import extract_playlist_info, download_playlist_tracks, create_zip_archive
from aiogram.types import FSInputFile
from services.deezer_service import search_track_deezer
from handlers.start import get_main_menu_kb, get_back_kb

router = Router()


class FetchStates(StatesGroup):
    waiting_for_query = State()
    waiting_for_playlist_action = State()


def download_track(title: str, artist: str, cover_url: str | None = None) -> dict | None:
    query = f"{artist} - {title}"
    
    file_hash = hashlib.md5(query.encode()).hexdigest()
    out_file_template = os.path.join(tempfile.gettempdir(), f"liminal_{file_hash}.%(ext)s")
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


@router.message(FetchStates.waiting_for_query)
async def process_search_query(message: Message, state: FSMContext):
    user_text = message.text
    
    if 'playlist' in user_text or 'album' in user_text:
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        playlist_info = await asyncio.to_thread(extract_playlist_info, user_text)
        
        if playlist_info:
            await state.update_data(playlist_info=playlist_info)
            await state.set_state(FetchStates.waiting_for_playlist_action)
            
            hours = playlist_info['total_duration'] // 3600
            minutes = (playlist_info['total_duration'] % 3600) // 60
            duration_str = f"{hours} ч {minutes} мин" if hours > 0 else f"{minutes} мин"
            
            caption = (
                f"🎵 **Плейлист: {playlist_info['title']}**\n"
                f"👤 Автор: *{playlist_info['uploader']}*\n"
                f"📊 Треков: {playlist_info['track_count']}\n"
                f"⏱ Общая длительность: {duration_str}\n\n"
                f"Как скачиваем?"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📦 Скачать архивом (.zip)", callback_data="playlist_download_zip"),
                    InlineKeyboardButton(text="📋 Показать список треков", callback_data="playlist_show_tracks")
                ],
                [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")]
            ])
            
            await message.answer(caption, reply_markup=keyboard, parse_mode="Markdown")
            return
    
    await message.bot.send_chat_action(chat_id=message.chat.id, action="upload_photo")
    
    track = await asyncio.to_thread(search_track_deezer, user_text)
    
    if track:
        await state.update_data(last_track=track)
        
        caption = (
            f"🎧 **{track['title']}**\n"
            f"👤 *{track['artist']}*\n"
            f"💿 Альбом: *{track['album']}*\n\n"
            f"Что делаем дальше?"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⬇️ Скачать", callback_data=f"dl_{track['deezer_id']}"),
                InlineKeyboardButton(text="❤️ В плейлист", callback_data=f"save_{track['deezer_id']}")
            ],
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")]
        ])
        
        if track['cover_url']:
            await message.answer_photo(
                photo=track['cover_url'],
                caption=caption,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            await message.answer(caption, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await message.answer(
            f"❌ Ничего не найдено по запросу *«{user_text}»*.\n\n"
            "Попробуй написать точнее или пришли ссылку.",
            reply_markup=get_back_kb(),
            parse_mode="Markdown"
        )

@router.callback_query(F.data == "back_to_main", FetchStates.waiting_for_query)
async def back_to_main_from_fetch(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    
    text = (
        f"🌑 **Добро пожаловать в LIMINAL**.\n\n"
        f"Музыка на пороге состояний.\n\n"
        f"Выбери действие ниже 👇"
    )
    
    await callback.message.edit_text(
        text, 
        reply_markup=get_main_menu_kb(), 
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dl_"))
async def handle_download(callback: CallbackQuery, state: FSMContext):
    deezer_id = callback.data.split("_", 1)[1]
    
    track_data = await state.get_data()
    if not track_data or 'last_track' not in track_data:
        await callback.answer("❌ Данные трека утеряны. Попробуй поискать заново.", show_alert=True)
        return
    
    track = track_data['last_track']
    
    status_message = await callback.message.answer(
        f"🎧 **{track['title']}** — *{track['artist']}*\n\n"
        "⏳ Ищу и скачиваю аудио...",
        parse_mode="Markdown"
    )
    await callback.answer()
    
    await callback.message.bot.send_chat_action(
        chat_id=callback.message.chat.id, 
        action="upload_voice"
    )
    
    result = await asyncio.to_thread(
        download_track, 
        track['title'], 
        track['artist'], 
        track.get('cover_url')
    )
    
    if not result:
        await status_message.edit_text(
            f"❌ Не удалось скачать *«{track['title']}»*.\n\n"
            "Попробуй другой трек или напиши точное название.",
            parse_mode="Markdown"
        )
        return
    
    await asyncio.to_thread(
        embed_cover_and_tags,
        result['file_path'],
        result['title'],
        result['artist'],
        result.get('cover_url'),
        track.get('album', '')
    )
    
    audio_file = FSInputFile(result['file_path'])
    await callback.message.answer_audio(
        audio=audio_file,
        title=result['title'],
        performer=result['artist'],
        caption=f"🎵 **{result['title']}**\n👤 *{result['artist']}*",
        parse_mode="Markdown"
    )
    
    
    await status_message.edit_text(
        f"✅ **{track['title']}** скачан и отправлен выше!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="️ Скачать ещё раз", callback_data=f"dl_{deezer_id}"),
                InlineKeyboardButton(text="❤️ В плейлист", callback_data=f"save_{deezer_id}")
            ],
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")]
        ]),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("save_"))
async def handle_save_to_playlist(callback: CallbackQuery, state: FSMContext):
    """Заглушка для кнопки 'В плейлист'"""
    await callback.answer("🚧 Функция сохранения будет доступна скоро!", show_alert=False)

@router.callback_query(FetchStates.waiting_for_playlist_action, F.data == "playlist_download_zip")
async def handle_playlist_download_zip(callback: CallbackQuery, state: FSMContext):
    """Скачивание плейлиста архивом"""
    track_data = await state.get_data()
    playlist_info = track_data.get('playlist_info')
    
    if not playlist_info:
        await callback.answer("❌ Данные плейлиста утеряны.", show_alert=True)
        return
    
    status_message = await callback.message.answer(
        f"🎵 **{playlist_info['title']}**\n\n"
        f"⏳ Скачиваю треки... (0/{playlist_info['track_count']})",
        parse_mode="Markdown"
    )
    await callback.answer()
    
    async def update_progress(current, total):
        await status_message.edit_text(
            f"🎵 **{playlist_info['title']}**\n\n"
            f"⏳ Скачиваю треки... ({current}/{total})",
            parse_mode="Markdown"
        )
    
    downloaded_files = await asyncio.to_thread(
        download_playlist_tracks, 
        playlist_info,
        lambda c, t: asyncio.run(update_progress(c, t))
    )
    
    if not downloaded_files:
        await status_message.edit_text(
            f"❌ Не удалось скачать ни одного трека из плейлиста.",
            parse_mode="Markdown"
        )
        return
    
    await status_message.edit_text(
        f"🎵 **{playlist_info['title']}**\n\n"
        f"✅ Скачано {len(downloaded_files)} треков. Создаю архив...",
        parse_mode="Markdown"
    )
    
    archive_path = await asyncio.to_thread(
        create_zip_archive, 
        downloaded_files, 
        f"liminal_{playlist_info['title'][:20]}"
    )
    
    if not archive_path:
        await status_message.edit_text(
            f"❌ Не удалось создать архив.",
            parse_mode="Markdown"
        )
        return
    
    archive_file = FSInputFile(archive_path)
    await callback.message.answer_document(
        document=archive_file,
        caption=f"🎵 **{playlist_info['title']}**\n📦 {len(downloaded_files)} треков",
        parse_mode="Markdown"
    )
    
    await status_message.edit_text(
        f"✅ **{playlist_info['title']}** скачан и отправлен выше!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")]
        ]),
        parse_mode="Markdown"
    )
    
    await state.clear()


@router.callback_query(FetchStates.waiting_for_playlist_action, F.data == "playlist_show_tracks")
async def handle_playlist_show_tracks(callback: CallbackQuery, state: FSMContext):
    track_data = await state.get_data()
    playlist_info = track_data.get('playlist_info')
    
    if not playlist_info:
        await callback.answer("❌ Данные плейлиста утеряны.", show_alert=True)
        return
    
    tracks_text = "\n".join([
        f"{i+1}. {t['artist']} — {t['title']}"
        for i, t in enumerate(playlist_info['tracks'][:20])
    ])
    
    if len(playlist_info['tracks']) > 20:
        tracks_text += f"\n\n... и ещё {len(playlist_info['tracks']) - 20} треков"
    
    text = (
        f"📋 **Список треков: {playlist_info['title']}**\n\n"
        f"{tracks_text}"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📦 Скачать архивом", callback_data="playlist_download_zip"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_playlist")
            ]
        ]),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_playlist")
async def back_to_playlist(callback: CallbackQuery, state: FSMContext):
    track_data = await state.get_data()
    playlist_info = track_data.get('playlist_info')
    
    if not playlist_info:
        await state.clear()
        await callback.message.edit_text(
            "🌑 **Добро пожаловать в LIMINAL**.\n\nВыбери действие ниже 👇",
            reply_markup=get_main_menu_kb(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return
    
    hours = playlist_info['total_duration'] // 3600
    minutes = (playlist_info['total_duration'] % 3600) // 60
    duration_str = f"{hours} ч {minutes} мин" if hours > 0 else f"{minutes} мин"
    
    caption = (
        f"🎵 **Плейлист: {playlist_info['title']}**\n"
        f"👤 Автор: *{playlist_info['uploader']}*\n"
        f"📊 Треков: {playlist_info['track_count']}\n"
        f"⏱ Общая длительность: {duration_str}\n\n"
        f"Как скачиваем?"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📦 Скачать архивом (.zip)", callback_data="playlist_download_zip"),
            InlineKeyboardButton(text="📋 Показать список треков", callback_data="playlist_show_tracks")
        ],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(caption, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()