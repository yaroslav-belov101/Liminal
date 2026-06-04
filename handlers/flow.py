import asyncio
import random
import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message, FSInputFile, URLInputFile
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from services.deezer_service import search_track_deezer, get_radio_tracks_by_genre
from services.youtube_service import download_track, embed_cover_and_tags
from services.database import (
    get_user_playlists, create_playlist, add_track_to_playlist,
    get_user_preferences, update_user_preference, add_to_user_list, reset_user_preferences
)
from handlers.start import get_main_menu_kb

router = Router()

class FlowStates(StatesGroup):
    main_menu = State()
    configuring = State()
    playing = State()
    choosing_playlist_to_save = State()
    naming_new_playlist_for_save = State()
    naming_preset = State()
    showing_stats = State()

TAGS = {
    "mood": {
        "melancholy": {"emoji": "🌧", "name": "Меланхолия", "kw": "sad melancholy acoustic"},
        "cheerful": {"emoji": "☀️", "name": "Веселое", "kw": "happy upbeat cheerful"},
        "energetic": {"emoji": "⚡", "name": "Энергичное", "kw": "energetic dance workout"},
        "night": {"emoji": "🌙", "name": "Ночное", "kw": "night chill ambient"},
        "focus": {"emoji": "🎯", "name": "Фокус", "kw": "focus concentration study"},
        "romance": {"emoji": "💖", "name": "Романтика", "kw": "romantic love ballad"}
    },
    "genre": {
        "pop": {"emoji": "🎤", "name": "Поп", "kw": "Pop"},
        "rock": {"emoji": "🎸", "name": "Рок", "kw": "Rock"},
        "hiphop": {"emoji": "🎧", "name": "Хип-хоп", "kw": "Hip-Hop"},
        "electronic": {"emoji": "🎹", "name": "Электроника", "kw": "Electronic"},
        "lofi": {"emoji": "📼", "name": "Лоу-фай", "kw": "Lo-Fi"},
        "indie": {"emoji": "🌿", "name": "Инди", "kw": "Indie"},
        "jazz": {"emoji": "🎷", "name": "Джаз", "kw": "Jazz"},
        "metal": {"emoji": "🤘", "name": "Метал", "kw": "Metal"},
        "rnb": {"emoji": "🎙", "name": "R&B", "kw": "RnB"},
        "phonk": {"emoji": "🚗", "name": "Фонк", "kw": "Phonk"}
    },
    "lang": {
        "russian": {"emoji": "🇷🇺", "name": "Русский", "kw": "russian"},
        "english": {"emoji": "🇬🇧", "name": "Английский", "kw": "english"},
        "japanese": {"emoji": "🇯🇵", "name": "Японский", "kw": "japanese"}
    }
}

SUBGENRES = {
    "Rock": ["Classic Rock", "Grunge", "Alternative Rock", "Post-Rock", "Indie Rock", "Punk Rock"],
    "Electronic": ["House", "Techno", "Ambient", "Synthwave", "Lo-Fi", "Drum and Bass"],
    "Pop": ["Synth Pop", "Indie Pop", "Dance Pop", "Art Pop"],
    "Hip-Hop": ["Old School", "Trap", "Boom Bap", "Cloud Rap", "Phonk"],
    "Jazz": ["Smooth Jazz", "Bebop", "Cool Jazz", "Fusion"],
    "Metal": ["Heavy Metal", "Thrash Metal", "Death Metal", "Doom Metal"],
    "RnB": ["Contemporary R&B", "Neo Soul", "Funk"],
    "Lo-Fi": ["Chillhop", "Jazzhop", "Ambient Beats"],
    "Indie": ["Dream Pop", "Shoegaze", "Folk"],
    "Phonk": ["Drift Phonk", "Jazz Phonk", "Atmospheric Phonk"]
}

ERAS = ["70s", "80s", "90s", "2000s", "2010s", "2020s"]

THEMATIC_WAVES = [
    {"name": "🌊 Сиэтл 90-х", "genre": "Rock", "mood": "melancholy", "era": "90s", "lang": "english"},
    {"name": "🌊 Манчестер 80-х", "genre": "Indie", "mood": "night", "era": "80s", "lang": "english"},
    {"name": "🌊 Токио 2020-х", "genre": "Pop", "mood": "cheerful", "era": "2020s", "lang": "japanese"},
    {"name": "🌊 Московский андеграунд", "genre": "Indie", "mood": "night", "era": "2010s", "lang": "russian"},
    {"name": "🌊 Лоу-фай для учёбы", "genre": "Lo-Fi", "mood": "focus", "era": "2020s", "lang": "english"},
    {"name": "🌊 Ретро-вейв", "genre": "Electronic", "mood": "night", "era": "80s", "lang": "english"},
    {"name": "🌊 Русская меланхолия", "genre": "Rock", "mood": "melancholy", "era": "90s", "lang": "russian"}
]

def weighted_random(weights_dict: dict, default_list: list):
    if not weights_dict:
        return random.choice(default_list)
    items = list(weights_dict.keys())
    weights = list(weights_dict.values())
    if sum(weights) == 0:
        return random.choice(items)
    return random.choices(items, weights=weights, k=1)[0]

@router.callback_query(F.data == "action_flow")
async def show_flow_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FlowStates.main_menu)
    text = (
        "🌊 **LIMINAL Flow**\n"
        "Умное радио, которое учится на твоих вкусах.\n\n"
        "🎲 **Быстрый старт** — тематические волны или рандом по вкусу.\n"
        "⚙️ **Настроить** — ручной выбор жанра, настроения и языка.\n"
        "📊 **Мой вкус** — статистика твоих предпочтений.\n"
        "💾 **Мои пресеты** — сохраненные комбинации."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Быстрый старт", callback_data="flow_quick_start")],
        [InlineKeyboardButton(text="⚙️ Настроить Flow", callback_data="flow_configure")],
        [InlineKeyboardButton(text="📊 Мой вкус", callback_data="flow_show_stats")],
        [InlineKeyboardButton(text="💾 Мои пресеты", callback_data="flow_show_presets")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "flow_quick_start", FlowStates.main_menu)
async def flow_quick_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FlowStates.playing)
    prefs = await get_user_preferences(callback.from_user.id)
    
    if random.random() < 0.3:
        wave = random.choice(THEMATIC_WAVES)
        genre_kw = next((g["kw"] for g in TAGS["genre"].values() if g["name"] == wave["genre"]), wave["genre"])
        mood_kw = next((m["kw"] for m in TAGS["mood"].values() if m["name"] == wave["mood"]), wave["mood"])
        lang_kw = next((l["kw"] for l in TAGS["lang"].values() if l["name"] == wave["lang"]), wave["lang"])
        era = wave["era"]
        await callback.answer(f"🌊 Волна: {wave['name']}")
    else:
        genre_name = weighted_random(prefs["genre_weights"], list(TAGS["genre"].keys()))
        mood_name = weighted_random(prefs["mood_weights"], list(TAGS["mood"].keys()))
        lang_name = weighted_random(prefs["lang_weights"], list(TAGS["lang"].keys()))
        
        genre_kw = TAGS["genre"][genre_name]["kw"]
        mood_kw = TAGS["mood"][mood_name]["kw"]
        lang_kw = TAGS["lang"][lang_name]["kw"]
        era = random.choice(ERAS)
        await callback.answer("🎲 Генерируем микс по твоему вкусу...")
        
    subgenre = random.choice(SUBGENRES.get(genre_kw, [genre_kw]))
    
    await state.update_data(
        selected_genres=[genre_kw],
        selected_moods=[mood_kw],
        selected_langs=[lang_kw],
        selected_era=era,
        selected_subgenre=subgenre,
        disliked_artists=prefs["disliked_artists"],
        played_track_ids=[]
    )
    await send_next_flow_track(callback, state)

@router.callback_query(F.data == "flow_configure", FlowStates.main_menu)
async def flow_configure(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FlowStates.configuring)
    prefs = await get_user_preferences(callback.from_user.id)
    await state.update_data(
        selected_moods=[], selected_genres=[], selected_langs=[],
        disliked_artists=prefs["disliked_artists"], played_track_ids=[]
    )
    await render_config_menu(callback, state)

async def render_config_menu(event: CallbackQuery | Message, state: FSMContext):
    data = await state.get_data()
    selected_moods = data.get("selected_moods", [])
    selected_genres = data.get("selected_genres", [])
    selected_langs = data.get("selected_langs", [])
    
    def build_kb(category, selected_list):
        buttons, row = [], []
        for key, tag in TAGS[category].items():
            prefix = "✅ " if tag["kw"] in selected_list else ""
            btn = InlineKeyboardButton(text=f"{prefix}{tag['emoji']} {tag['name']}", callback_data=f"flow_toggle_{category}_{key}")
            row.append(btn)
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row: buttons.append(row)
        return buttons

    active_tags_count = len(selected_moods) + len(selected_genres) + len(selected_langs)
    start_text = "▶️ Запустить Flow" if active_tags_count > 0 else "⚠️ Выбери хотя бы 1 тег"
    start_callback = "flow_start_custom" if active_tags_count > 0 else "flow_configure"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 Настроение", callback_data="noop")], *build_kb("mood", selected_moods),
        [InlineKeyboardButton(text="🎸 Жанр", callback_data="noop")], *build_kb("genre", selected_genres),
        [InlineKeyboardButton(text="🌍 Язык", callback_data="noop")], *build_kb("lang", selected_langs),
        [
            InlineKeyboardButton(text="🔄 Сбросить", callback_data="flow_reset_tags"),
            InlineKeyboardButton(text="💾 Сохранить пресет", callback_data="flow_save_preset")
        ],
        [InlineKeyboardButton(text=start_text, callback_data=start_callback)],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="action_flow")]
    ])
    
    text = f"⚙️ **Настройка Flow**\nНажми на теги, чтобы выбрать их.\nАктивных тегов: {active_tags_count}"
    
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await event.answer()
    else:
        await event.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data.startswith("flow_toggle_"), FlowStates.configuring)
async def flow_toggle_tag(callback: CallbackQuery, state: FSMContext):
    _, _, category, key = callback.data.split("_")
    tag_kw = TAGS[category][key]["kw"]
    data = await state.get_data()
    current_list = data.get(f"selected_{category}s", [])
    
    if tag_kw in current_list:
        current_list.remove(tag_kw)
    else:
        current_list.append(tag_kw)
        
    await state.update_data(**{f"selected_{category}s": current_list})
    await render_config_menu(callback, state)

@router.callback_query(F.data == "flow_reset_tags", FlowStates.configuring)
async def flow_reset_tags(callback: CallbackQuery, state: FSMContext):
    await state.update_data(selected_moods=[], selected_genres=[], selected_langs=[])
    await render_config_menu(callback, state)

@router.callback_query(F.data == "flow_save_preset", FlowStates.configuring)
async def flow_ask_preset_name(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FlowStates.naming_preset)
    text = "💾 **Сохранить пресет**\nНапиши название для этой комбинации:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="flow_configure")]])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.message(FlowStates.naming_preset)
async def flow_process_preset_name(message: Message, state: FSMContext):
    name = message.text.strip()[:30]
    data = await state.get_data()
    
    tags_summary = []
    for kw in data.get("selected_moods", []):
        tags_summary.append(next(t["name"] for t in TAGS["mood"].values() if t["kw"] == kw))
    for kw in data.get("selected_genres", []):
        tags_summary.append(next(t["name"] for t in TAGS["genre"].values() if t["kw"] == kw))
    for kw in data.get("selected_langs", []):
        tags_summary.append(next(t["name"] for t in TAGS["lang"].values() if t["kw"] == kw))
        
    preset_name = f"🌊 PRESET: {name} | {'-'.join(tags_summary)}"
    await create_playlist(message.from_user.id, preset_name)
    
    await message.answer(f"✅ Пресет **\"{name}\"** сохранен!", parse_mode="Markdown")
    await state.set_state(FlowStates.configuring)
    await render_config_menu(message, state)

@router.callback_query(F.data == "flow_show_presets", FlowStates.main_menu)
async def flow_show_presets(callback: CallbackQuery, state: FSMContext):
    playlists = await get_user_playlists(callback.from_user.id)
    presets = [p for p in playlists if p["name"].startswith("🌊 PRESET:")]
    
    if not presets:
        text = "💾 **Мои пресеты**\nУ тебя пока нет сохраненных пресетов."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Настроить Flow", callback_data="flow_configure")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="action_flow")]
        ])
    else:
        text = "💾 **Мои пресеты**\nВыбери сохраненную комбинацию:"
        kb_buttons = [[InlineKeyboardButton(text=f"▶️ {p['name'].replace('🌊 PRESET: ', '').split(' | ')[0]}", callback_data=f"flow_load_preset_{p['id']}")] for p in presets[:9]]
        kb_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="action_flow")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
        
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("flow_load_preset_"))
async def flow_load_preset(callback: CallbackQuery, state: FSMContext):
    playlist_id = int(callback.data.split("_")[3])
    playlists = await get_user_playlists(callback.from_user.id)
    preset = next((p for p in playlists if p["id"] == playlist_id), None)
    
    if not preset:
        await callback.answer("❌ Пресет не найден", show_alert=True)
        return
        
    parts = preset["name"].replace("🌊 PRESET: ", "").split(" | ")
    selected_tags = parts[1].split("-") if len(parts) > 1 else []
    
    selected_moods, selected_genres, selected_langs = [], [], []
    for tag_name in selected_tags:
        for t in TAGS["mood"].values():
            if t["name"] == tag_name: selected_moods.append(t["kw"])
        for t in TAGS["genre"].values():
            if t["name"] == tag_name: selected_genres.append(t["kw"])
        for t in TAGS["lang"].values():
            if t["name"] == tag_name: selected_langs.append(t["kw"])
            
    prefs = await get_user_preferences(callback.from_user.id)
    await state.update_data(
        selected_moods=selected_moods, selected_genres=selected_genres, selected_langs=selected_langs,
        disliked_artists=prefs["disliked_artists"], played_track_ids=[]
    )
    await state.set_state(FlowStates.playing)
    await callback.answer(f"▶️ Загружен пресет: {parts[0]}")
    await send_next_flow_track(callback, state)

@router.callback_query(F.data == "flow_start_custom", FlowStates.configuring)
async def flow_start_custom(callback: CallbackQuery, state: FSMContext):
    prefs = await get_user_preferences(callback.from_user.id)
    await state.update_data(disliked_artists=prefs["disliked_artists"], played_track_ids=[])
    await state.set_state(FlowStates.playing)
    await callback.answer()
    await send_next_flow_track(callback, state)

async def send_next_flow_track(callback: CallbackQuery | Message, state: FSMContext):
    data = await state.get_data()
    old_message_id = data.get("player_message_id")
    
    moods = data.get("selected_moods", [])
    genres = data.get("selected_genres", [])
    langs = data.get("selected_langs", [])
    era = data.get("selected_era", random.choice(ERAS))
    subgenre = data.get("selected_subgenre", genres[0] if genres else "Pop")
    
    disliked = [d.lower() for d in data.get("disliked_artists", [])]
    played_ids = data.get("played_track_ids", [])
    
    genre_for_api = genres[0] if genres else None
    lang_for_api = langs[0] if langs else None
    keywords = " ".join(moods) if moods else "top hits"
    
    search_strategies = []
    if lang_for_api == "russian":
        search_strategies.append({"type": "search", "query": keywords, "genre": None, "lang": "russian"})
    if genre_for_api and keywords != "top hits":
        search_strategies.append({"type": "search", "query": f"{keywords} {era}", "genre": genre_for_api, "lang": None})
    if keywords != "top hits":
        search_strategies.append({"type": "search", "query": f"{keywords} {era}", "genre": None, "lang": None})
    if genre_for_api:
        search_strategies.append({"type": "radio", "genre": genre_for_api})
    search_strategies.extend([
        {"type": "search", "query": "chill mix", "genre": None, "lang": None},
        {"type": "search", "query": "top hits", "genre": None, "lang": None}
    ])
    
    status_msg = None
    if isinstance(callback, CallbackQuery):
        chat_id = callback.message.chat.id
        bot = callback.message.bot
        status_msg = await bot.send_message(chat_id, "⏳ Подбираю трек и загружаю...")
        await callback.answer()
    else:
        chat_id = callback.chat.id
        bot = callback.bot

    track = None
    for strategy in search_strategies:
        if strategy["type"] == "search":
            track = await asyncio.to_thread(
                search_track_deezer, strategy["query"], genre=strategy["genre"], 
                exclude_ids=played_ids, limit=10, lang=strategy.get("lang")
            )
        elif strategy["type"] == "radio":
            track = await asyncio.to_thread(get_radio_tracks_by_genre, strategy["genre"], exclude_ids=played_ids)
            
        if track and track["artist"].lower() not in disliked:
            break
        track = None
        
    if not track:
        msg_text = "❌ Не удалось подобрать трек. Попробуй изменить фильтры."
        if status_msg:
            await status_msg.edit_text(msg_text)
        else:
            await bot.send_message(chat_id, msg_text)
        await state.clear()
        return
        
    if old_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=old_message_id)
        except Exception:
            pass
            
    await bot.send_chat_action(chat_id=chat_id, action="upload_voice")
    
    result = await asyncio.to_thread(download_track, track['title'], track['artist'], track.get('cover_url'))
    
    if not result:
        if status_msg:
            await status_msg.edit_text("❌ Ошибка загрузки аудио. Пробую другой трек...")
        await asyncio.sleep(1)
        if isinstance(callback, CallbackQuery):
            await send_next_flow_track(callback, state)
        return

    await asyncio.to_thread(embed_cover_and_tags, result['file_path'], result['title'], result['artist'], result.get('cover_url'), track.get('album', ''))
    
    audio_file = FSInputFile(result['file_path'])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Забрать", callback_data="flow_like"), InlineKeyboardButton(text="👎 Не зашло", callback_data="flow_dislike")],
        [InlineKeyboardButton(text="⏭ Дальше", callback_data="flow_next"), InlineKeyboardButton(text="⏹ Стоп", callback_data="flow_stop")]
    ])
    
    caption = f"🎧 **{track['title']}**\n👤 *{track['artist']}*\n💿 Альбом: *{track['album']}*"
    thumbnail = URLInputFile(track['cover_url']) if track.get('cover_url') else None
    
    msg = await bot.send_audio(
        chat_id=chat_id, audio=audio_file, title=track['title'], performer=track['artist'],
        caption=caption, parse_mode="Markdown", reply_markup=keyboard, thumbnail=thumbnail
    )
    
    if status_msg:
        await status_msg.delete()
        
    new_played_ids = played_ids + [track['deezer_id']]
    if len(new_played_ids) > 50:
        new_played_ids = new_played_ids[-50:]
        
    await state.update_data(current_flow_track=track, player_message_id=msg.message_id, played_track_ids=new_played_ids)

@router.callback_query(F.data == "flow_next", FlowStates.playing)
async def flow_next(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await send_next_flow_track(callback, state)

@router.callback_query(F.data == "flow_like", FlowStates.playing)
async def flow_like(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    track = data.get("current_flow_track")
    if not track:
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return
        
    user_id = callback.from_user.id
    await update_user_preference(user_id, "genre", data.get("selected_genres", ["Pop"])[0], 1.0)
    await update_user_preference(user_id, "mood", data.get("selected_moods", ["melancholy"])[0], 1.0)
    if data.get("selected_langs"):
        await update_user_preference(user_id, "lang", data["selected_langs"][0], 1.0)
    await add_to_user_list(user_id, "liked_artists", track["artist"])
    
    await state.update_data(pending_save_track=track)
    await state.set_state(FlowStates.choosing_playlist_to_save)
    
    playlists = await get_user_playlists(user_id)
    real_playlists = [p for p in playlists if not p["name"].startswith("🌊 PRESET:")]
    
    if not real_playlists:
        text = f"❤️ **Сохранить \"{track['title']}\"**\nУ тебя пока нет плейлистов.\nСоздай первый плейлист!"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать новый", callback_data="flow_create_playlist_for_track")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="flow_cancel_save")]
        ])
    else:
        text = f"❤️ **Сохранить \"{track['title']}\" в плейлист:**"
        kb_buttons = [[InlineKeyboardButton(text=f"📼 {p['name']} ({p['track_count']})", callback_data=f"flow_save_to_pl_{p['id']}")] for p in real_playlists[:9]]
        kb_buttons.append([InlineKeyboardButton(text="➕ Создать новый", callback_data="flow_create_playlist_for_track")])
        kb_buttons.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="flow_cancel_save")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
        
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "flow_create_playlist_for_track", FlowStates.choosing_playlist_to_save)
async def flow_ask_new_playlist_name(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FlowStates.naming_new_playlist_for_save)
    text = "➕ **Создание плейлиста**\nНапиши название:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="flow_cancel_save")]])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.message(FlowStates.naming_new_playlist_for_save)
async def flow_process_new_playlist(message: Message, state: FSMContext):
    name = message.text.strip()[:50]
    data = await state.get_data()
    track = data.get("pending_save_track")
    
    playlist_id = await create_playlist(message.from_user.id, name)
    if track:
        await add_track_to_playlist(playlist_id, message.from_user.id, track["deezer_id"], track["title"], track["artist"], track.get("album", ""), track.get("cover_url", ""))
        await message.answer(f"✅ Плейлист **\"{name}\"** создан!\nТрек **{track['title']}** добавлен.", parse_mode="Markdown")
    else:
        await message.answer(f"✅ Плейлист **\"{name}\"** создан!", parse_mode="Markdown")
        
    await state.set_state(FlowStates.playing)
    await send_next_flow_track(message, state)

@router.callback_query(F.data.startswith("flow_save_to_pl_"), FlowStates.choosing_playlist_to_save)
async def flow_save_to_selected_playlist(callback: CallbackQuery, state: FSMContext):
    playlist_id = int(callback.data.split("_")[4])
    data = await state.get_data()
    track = data.get("pending_save_track")
    
    if not track:
        await callback.answer("❌ Данные трека утеряны", show_alert=True)
        await state.set_state(FlowStates.playing)
        return
        
    added = await add_track_to_playlist(playlist_id, callback.from_user.id, track["deezer_id"], track["title"], track["artist"], track.get("album", ""), track.get("cover_url", ""))
    playlists = await get_user_playlists(callback.from_user.id)
    pl_name = next((p["name"] for p in playlists if p["id"] == playlist_id), "Неизвестно")
    
    await callback.answer(f"✅ Добавлено в \"{pl_name}\"!" if added else "⚠️ Трек уже есть!", show_alert=not added)
    await state.set_state(FlowStates.playing)
    await send_next_flow_track(callback, state)

@router.callback_query(F.data == "flow_cancel_save", F.state.in_([FlowStates.choosing_playlist_to_save, FlowStates.naming_new_playlist_for_save]))
async def flow_cancel_save(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FlowStates.playing)
    await callback.answer("❌ Сохранение отменено")
    await send_next_flow_track(callback, state)

@router.callback_query(F.data == "flow_dislike", FlowStates.playing)
async def flow_dislike(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    track = data.get("current_flow_track")
    
    if track:
        user_id = callback.from_user.id
        current_genre = data.get("selected_genres", ["Pop"])[0]
        await update_user_preference(user_id, "genre", current_genre, -0.3)
        await add_to_user_list(user_id, "disliked_artists", track["artist"])
        await state.update_data(disliked_artists=data.get("disliked_artists", []) + [track["artist"]])
            
    await callback.answer("👎 Трек пропущен, артист в игноре")
    await send_next_flow_track(callback, state)

@router.callback_query(F.data == "flow_stop", FlowStates.playing)
async def flow_stop(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    old_message_id = data.get("player_message_id")
    await state.clear()
    await callback.answer("⏹ Flow остановлен")
    
    if old_message_id:
        try:
            await callback.message.bot.delete_message(chat_id=callback.message.chat.id, message_id=old_message_id)
        except Exception:
            pass
            
    text = "🌑 **Добро пожаловать в LIMINAL**.\nМузыка на пороге состояний.\nВыбери действие ниже 👇"
    await callback.message.answer(text, reply_markup=get_main_menu_kb(), parse_mode="Markdown")

@router.callback_query(F.data == "flow_show_stats", FlowStates.main_menu)
async def flow_show_stats(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FlowStates.showing_stats)
    prefs = await get_user_preferences(callback.from_user.id)
    
    def format_weights(weights_dict, tag_dict):
        if not weights_dict:
            return "Нет данных"
        sorted_items = sorted(weights_dict.items(), key=lambda x: x[1], reverse=True)[:3]
        result = []
        for key, weight in sorted_items:
            name = next((t["name"] for t in tag_dict.values() if t["kw"] == key), key)
            result.append(f"{name} ({weight:.1f})")
        return ", ".join(result)

    genre_stats = format_weights(prefs["genre_weights"], TAGS["genre"])
    mood_stats = format_weights(prefs["mood_weights"], TAGS["mood"])
    lang_stats = format_weights(prefs["lang_weights"], TAGS["lang"])
    liked_count = len(prefs["liked_artists"])
    disliked_count = len(prefs["disliked_artists"])

    text = (
        "📊 **Твой музыкальный вкус**\n\n"
        f"🎸 **Любимые жанры:** {genre_stats}\n"
        f"🎭 **Настроения:** {mood_stats}\n"
        f"🌍 **Языки:** {lang_stats}\n\n"
        f"❤️ Понравилось артистов: {liked_count}\n"
        f"👎 В игноре артистов: {disliked_count}\n\n"
        "Бот становится умнее с каждым твоим лайком!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Сбросить вкус", callback_data="flow_confirm_reset")],
        [InlineKeyboardButton(text="🔙 Назад в Flow", callback_data="action_flow")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "flow_confirm_reset", FlowStates.showing_stats)
async def flow_confirm_reset(callback: CallbackQuery, state: FSMContext):
    text = "⚠️ **Сбросить профиль вкуса?**\nВсе накопленные предпочтения будут удалены. Это действие нельзя отменить."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, сбросить", callback_data="flow_execute_reset")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="flow_show_stats")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "flow_execute_reset", FlowStates.showing_stats)
async def flow_execute_reset(callback: CallbackQuery, state: FSMContext):
    await reset_user_preferences(callback.from_user.id)
    await callback.answer("✅ Профиль вкуса сброшен!")
    await flow_show_stats(callback, state)