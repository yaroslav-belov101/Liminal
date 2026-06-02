from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import asyncio
import os
from services.database import (
    create_user, get_user_playlists, create_playlist, get_playlist_tracks,
    delete_playlist, get_playlist_info, add_track_to_playlist,
    remove_track_from_playlist, track_exists_in_playlist, rename_playlist
)
from handlers.start import get_main_menu_kb, get_back_kb

router = Router()

class PlaylistStates(StatesGroup):
    waiting_for_playlist_name = State()
    waiting_for_rename = State()
    playing_playlist = State()

@router.callback_query(F.data == "action_playlists")
async def show_playlists_menu(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    username = callback.from_user.full_name or "Пользователь"
    await create_user(user_id, username)
    playlists = await get_user_playlists(user_id)
    
    if not playlists:
        text = "🎛 **Твои плейлисты**\nУ тебя пока нет плейлистов.\nНажми кнопку ниже, чтобы создать первый!"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать плейлист", callback_data="create_new_playlist")],
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")]
        ])
    else:
        text = "🎛 **Твои плейлисты**\n"
        keyboard_buttons = []
        for playlist in playlists[:10]:
            row = [InlineKeyboardButton(
                text=f"📼 {playlist['name']} ({playlist['track_count']})",
                callback_data=f"playlist_open_{playlist['id']}"
            )]
            keyboard_buttons.append(row)
        keyboard_buttons.append([InlineKeyboardButton(text="➕ Создать плейлист", callback_data="create_new_playlist")])
        keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "create_new_playlist")
async def start_create_playlist(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PlaylistStates.waiting_for_playlist_name)
    text = "➕ **Создание нового плейлиста**\nНапиши название для нового плейлиста:\nНапример: *Ночной вайб*, *Для работы*, *Избранное*"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="action_playlists")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.message(PlaylistStates.waiting_for_playlist_name)
async def process_create_playlist(message: Message, state: FSMContext):
    playlist_name = message.text.strip()
    if len(playlist_name) > 50:
        await message.answer("❌ Название слишком длинное (максимум 50 символов).\nПопробуй короче.")
        return
        
    user_id = message.from_user.id
    playlist_id = await create_playlist(user_id, playlist_name)
    track_data = await state.get_data()
    pending_deezer_id = track_data.get('pending_track_deezer_id')
    await state.clear()
    
    if pending_deezer_id:
        track = track_data.get('last_track')
        if track:
            await add_track_to_playlist(
                playlist_id=playlist_id, user_id=user_id, deezer_id=pending_deezer_id,
                title=track['title'], artist=track['artist'], album=track.get('album', ''), cover_url=track.get('cover_url', '')
            )
            await message.answer(f"✅ Плейлист **\"{playlist_name}\"** создан!\nТрек **{track['title']}** добавлен в него.", reply_markup=get_main_menu_kb(), parse_mode="Markdown")
            return
            
    await message.answer(f"✅ Плейлист **\"{playlist_name}\"** создан!\nТеперь ты можешь добавлять в него треки.", reply_markup=get_main_menu_kb(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("playlist_open_"))
async def open_playlist(callback: CallbackQuery, state: FSMContext):
    playlist_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    playlist_info = await get_playlist_info(playlist_id, user_id)
    if not playlist_info:
        await callback.answer("❌ Плейлист не найден.", show_alert=True)
        return
        
    tracks = await get_playlist_tracks(playlist_id, user_id)
    tracks_per_page = 10
    total_pages = (len(tracks) + tracks_per_page - 1) // tracks_per_page if tracks else 1
    
    text = f"📼 **{playlist_info['name']}**\n{playlist_info['track_count']} треков\n"
    if tracks:
        for i, track in enumerate(tracks[:tracks_per_page], 1):
            text += f"{i}. **{track['artist']}** — {track['title']}\n"
        if len(tracks) > tracks_per_page:
            text += f"\n... и ещё {len(tracks) - tracks_per_page} треков"
    else:
        text += "Плейлист пуст. Добавь треки через поиск!"
        
    keyboard_buttons = []
    if tracks:
        keyboard_buttons.append([InlineKeyboardButton(text="▶️ Воспроизвести", callback_data=f"playlist_play_{playlist_id}_0")])
        if total_pages > 1:
            keyboard_buttons.append([InlineKeyboardButton(text="📄 Все треки", callback_data=f"playlist_page_{playlist_id}_0")])
    keyboard_buttons.append([
        InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"playlist_rename_{playlist_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"playlist_delete_{playlist_id}")
    ])
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 К списку плейлистов", callback_data="action_playlists")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("playlist_delete_"))
async def delete_playlist_handler(callback: CallbackQuery, state: FSMContext):
    playlist_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    playlist_info = await get_playlist_info(playlist_id, user_id)
    if not playlist_info:
        await callback.answer("❌ Плейлист не найден.", show_alert=True)
        return
        
    text = f"⚠️ **Удалить плейлист \"{playlist_info['name']}\"?**\nВсе {playlist_info['track_count']} треков будут удалены.\nЭто действие нельзя отменить."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{playlist_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"playlist_open_{playlist_id}")
        ]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_playlist(callback: CallbackQuery, state: FSMContext):
    playlist_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    deleted = await delete_playlist(playlist_id, user_id)
    if deleted:
        await callback.answer("✅ Плейлист удалён!")
        await show_playlists_menu(callback, state)
    else:
        await callback.answer("❌ Ошибка при удалении.", show_alert=True)

@router.callback_query(F.data.startswith("playlist_rename_"))
async def start_rename_playlist(callback: CallbackQuery, state: FSMContext):
    playlist_id = int(callback.data.split("_")[2])
    await state.update_data(renaming_playlist_id=playlist_id)
    await state.set_state(PlaylistStates.waiting_for_rename)
    text = "✏️ **Переименование плейлиста**\nНапиши новое название:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"playlist_open_{playlist_id}")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.message(PlaylistStates.waiting_for_rename)
async def process_rename_playlist(message: Message, state: FSMContext):
    new_name = message.text.strip()
    if len(new_name) > 50:
        await message.answer("❌ Название слишком длинное (максимум 50 символов).\nПопробуй короче.")
        return
        
    track_data = await state.get_data()
    playlist_id = track_data.get('renaming_playlist_id')
    if not playlist_id:
        await message.answer("❌ Ошибка. Попробуй снова.")
        await state.clear()
        return
        
    renamed = await rename_playlist(playlist_id, message.from_user.id, new_name)
    await state.clear()
    if renamed:
        await message.answer(f"✅ Плейлист переименован в **\"{new_name}\"**!", parse_mode="Markdown")
    else:
        await message.answer("❌ Ошибка при переименовании.")

@router.callback_query(F.data.startswith("playlist_remove_track_"))
async def remove_track_handler(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    track_id = int(parts[3])
    playlist_id = int(parts[4])
    user_id = callback.from_user.id
    removed = await remove_track_from_playlist(track_id, playlist_id, user_id)
    if removed:
        await callback.answer("✅ Трек удалён из плейлиста!")
        await open_playlist(callback, state)
    else:
        await callback.answer("❌ Ошибка при удалении трека.", show_alert=True)

@router.callback_query(F.data.startswith("playlist_play_"))
async def start_playing_playlist(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    playlist_id = int(parts[2])
    track_index = int(parts[3])
    user_id = callback.from_user.id
    
    playlist_info = await get_playlist_info(playlist_id, user_id)
    if not playlist_info:
        await callback.answer("❌ Плейлист не найден.", show_alert=True)
        return
        
    tracks = await get_playlist_tracks(playlist_id, user_id)
    if not tracks or track_index >= len(tracks):
        await callback.answer("❌ Треки не найдены.", show_alert=True)
        return
        
    await state.update_data(current_playlist_id=playlist_id, current_track_index=track_index)
    await state.set_state(PlaylistStates.playing_playlist)
    await send_current_track(callback, state, tracks, track_index)

async def send_current_track(callback: CallbackQuery, state: FSMContext, tracks: list, track_index: int):
    track = tracks[track_index]
    from services.youtube_service import download_track, embed_cover_and_tags
    
    result = await asyncio.to_thread(download_track, track['title'], track['artist'], track.get('cover_url'))
    if not result:
        await callback.message.answer(f"❌ Не удалось скачать трек: {track['artist']} — {track['title']}\nПропускаю...", parse_mode="Markdown")
        await callback.answer()
        return
        
    await asyncio.to_thread(embed_cover_and_tags, result['file_path'], result['title'], result['artist'], result.get('cover_url'), track.get('album', ''))
    audio_file = FSInputFile(result['file_path'])
    playlist_data = await state.get_data()
    playlist_id = playlist_data.get('current_playlist_id')
    
    keyboard_buttons = []
    nav_buttons = []
    if track_index > 0:
        nav_buttons.append(InlineKeyboardButton(text="⏮ Пред.", callback_data=f"playlist_play_{playlist_id}_{track_index - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"🎵 {track_index + 1}/{len(tracks)}", callback_data="noop"))
    if track_index < len(tracks) - 1:
        nav_buttons.append(InlineKeyboardButton(text="⏭ След.", callback_data=f"playlist_play_{playlist_id}_{track_index + 1}"))
        
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)
    keyboard_buttons.append([InlineKeyboardButton(text="⏹ Стоп", callback_data="stop_playlist")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.answer_audio(
        audio=audio_file,
        title=result['title'],
        performer=result['artist'],
        caption=f"🎵 **{result['title']}**\n👤 *{result['artist']}*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "stop_playlist")
async def stop_playlist(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("⏹ Воспроизведение остановлено")
    playlist_data = await state.get_data()
    playlist_id = playlist_data.get('current_playlist_id')
    if playlist_id:
        await open_playlist(callback, state)
    else:
        await show_playlists_menu(callback, state)

@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data == "back_to_main", F.state.in_([PlaylistStates.waiting_for_playlist_name, PlaylistStates.waiting_for_rename, PlaylistStates.playing_playlist]))
async def back_to_main_from_playlist(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "🌑 **Добро пожаловать в LIMINAL**.\nМузыка на пороге состояний.\nВыбери действие ниже 👇"
    await callback.message.edit_text(text, reply_markup=get_main_menu_kb(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("add_to_playlist_"))
async def add_track_to_playlist_handler(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    playlist_id = int(parts[3])
    deezer_id = parts[4]
    track_data = await state.get_data()
    track = track_data.get('last_track')
    if not track:
        await callback.answer("❌ Данные трека утеряны.", show_alert=True)
        return
        
    user_id = callback.from_user.id
    exists = await track_exists_in_playlist(playlist_id, deezer_id)
    if exists:
        await callback.answer("⚠️ Трек уже есть в этом плейлисте!", show_alert=False)
        return
        
    added = await add_track_to_playlist(
        playlist_id=playlist_id, user_id=user_id, deezer_id=deezer_id,
        title=track['title'], artist=track['artist'], album=track.get('album', ''), cover_url=track.get('cover_url', '')
    )
    playlist_info = await get_playlist_info(playlist_id, user_id)
    playlist_name = playlist_info['name'] if playlist_info else "Неизвестно"
    
    if added:
        await callback.answer(f"✅ Добавлено в \"{playlist_name}\"!")
        text = (
            f"🎧 **{track['title']}**\n"
            f"👤 *{track['artist']}*\n"
            f"💿 Альбом: *{track['album']}*\n"
            f"✅ Сохранено в **\"{playlist_name}\"**!\n"
            f"Что делаем дальше?"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⬇️ Скачать", callback_data=f"dl_{deezer_id}"),
                InlineKeyboardButton(text="❤️ Ещё в плейлист", callback_data=f"save_{deezer_id}")
            ],
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")]
        ])
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await callback.answer("❌ Ошибка при добавлении.", show_alert=True)

@router.callback_query(F.data.startswith("create_playlist_from_track_"))
async def create_playlist_from_track(callback: CallbackQuery, state: FSMContext):
    deezer_id = callback.data.split("_")[4]
    await state.update_data(pending_track_deezer_id=deezer_id)
    await state.set_state(PlaylistStates.waiting_for_playlist_name)
    text = "➕ **Создание нового плейлиста**\nНапиши название для нового плейлиста:\nПосле создания трек будет автоматически добавлен в него."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("playlist_page_"))
async def playlist_pagination(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    playlist_id = int(parts[2])
    page = int(parts[3])
    user_id = callback.from_user.id
    
    playlist_info = await get_playlist_info(playlist_id, user_id)
    if not playlist_info:
        await callback.answer("❌ Плейлист не найден.", show_alert=True)
        return
        
    tracks = await get_playlist_tracks(playlist_id, user_id)
    tracks_per_page = 10
    total_pages = (len(tracks) + tracks_per_page - 1) // tracks_per_page
    start_idx = page * tracks_per_page
    end_idx = start_idx + tracks_per_page
    page_tracks = tracks[start_idx:end_idx]
    
    text = f"📼 **{playlist_info['name']}**\n{playlist_info['track_count']} треков\n"
    for i, track in enumerate(page_tracks, start_idx + 1):
        text += f"{i}. **{track['artist']}** — {track['title']}\n"
    text += f"\n📄 Страница {page + 1} из {total_pages}"
    
    keyboard_buttons = []
    if tracks:
        keyboard_buttons.append([InlineKeyboardButton(text="▶️ Воспроизвести", callback_data=f"playlist_play_{playlist_id}_0")])
        
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"playlist_page_{playlist_id}_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"playlist_page_{playlist_id}_{page + 1}"))
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)
        
    keyboard_buttons.append([
        InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"playlist_rename_{playlist_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"playlist_delete_{playlist_id}")
    ])
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 К списку плейлистов", callback_data="action_playlists")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()