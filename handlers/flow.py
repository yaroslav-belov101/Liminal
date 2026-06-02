import asyncio
import random
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from services.deezer_service import search_track_deezer
from handlers.start import get_main_menu_kb

router = Router()

class FlowStates(StatesGroup):
    choosing_mood = State()
    playing = State()

MOODS = {
    "melancholy": {"emoji": "🌧", "name": "Меланхолия", "keywords": "sad chill melancholy acoustic"},
    "cheerful": {"emoji": "☀️", "name": "Веселое", "keywords": "happy upbeat cheerful pop"},
    "energetic": {"emoji": "⚡", "name": "Энергичное", "keywords": "energetic rock electronic dance"},
    "night": {"emoji": "🌙", "name": "Ночное", "keywords": "night lofi synthwave ambient"}
}

@router.callback_query(F.data == "action_flow")
async def show_flow_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FlowStates.choosing_mood)
    text = "🌊 **Flow**\nЛовим какую волну? Выбери настроение, и я подберу музыку."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌧 Меланхолия", callback_data="flow_mood_melancholy"),
            InlineKeyboardButton(text="☀️ Веселое", callback_data="flow_mood_cheerful")
        ],
        [
            InlineKeyboardButton(text="⚡ Энергичное", callback_data="flow_mood_energetic"),
            InlineKeyboardButton(text="🌙 Ночное", callback_data="flow_mood_night")
        ],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("flow_mood_"), FlowStates.choosing_mood)
async def start_flow(callback: CallbackQuery, state: FSMContext):
    mood_key = callback.data.split("_")[2]
    mood = MOODS.get(mood_key)
    if not mood:
        await callback.answer("❌ Неизвестное настроение", show_alert=True)
        return
    
    await state.update_data(current_mood=mood_key, mood_keywords=mood["keywords"])
    await state.set_state(FlowStates.playing)
    await callback.answer()
    await send_next_flow_track(callback, state, mood["keywords"])

async def send_next_flow_track(callback: CallbackQuery, state: FSMContext, keywords: str):
    random_queries = [
        f"{keywords} music",
        f"best {keywords} songs",
        f"{keywords} mix",
        f"top {keywords} tracks"
    ]
    query = random.choice(random_queries)
    
    await callback.message.bot.send_chat_action(chat_id=callback.message.chat.id, action="typing")
    
    track = await asyncio.to_thread(search_track_deezer, query)
    if not track:
        track = await asyncio.to_thread(search_track_deezer, keywords.split()[0])
        
    if not track:
        await callback.message.answer("❌ Не удалось найти трек. Попробуй другое настроение.", reply_markup=get_main_menu_kb())
        await state.clear()
        return

    await state.update_data(current_flow_track=track)
    
    text = f"🎧 **{track['title']}**\n👤 *{track['artist']}*\n💿 Альбом: *{track['album']}*"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Забрать", callback_data="flow_like"),
            InlineKeyboardButton(text="👎 Не зашло", callback_data="flow_dislike")
        ],
        [
            InlineKeyboardButton(text="⏭ Дальше", callback_data="flow_next"),
            InlineKeyboardButton(text="⏹ Стоп", callback_data="flow_stop")
        ]
    ])
    
    if track.get('cover_url'):
        await callback.message.answer_photo(
            photo=track['cover_url'],
            caption=text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "flow_next", FlowStates.playing)
async def flow_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    keywords = data.get("mood_keywords", "music")
    await callback.answer()
    await send_next_flow_track(callback, state, keywords)

@router.callback_query(F.data == "flow_like", FlowStates.playing)
async def flow_like(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    track = data.get("current_flow_track")
    if track:
        await callback.answer(f"❤️ Трек \"{track['title']}\" запомнен!")
    else:
        await callback.answer("❤️ Запомнил!")
    
    keywords = data.get("mood_keywords", "music")
    await send_next_flow_track(callback, state, keywords)

@router.callback_query(F.data == "flow_dislike", FlowStates.playing)
async def flow_dislike(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    track = data.get("current_flow_track")
    if track:
        await callback.answer(f"👎 Трек \"{track['title']}\" пропущен.")
    else:
        await callback.answer("👎 Пропущено.")
    
    keywords = data.get("mood_keywords", "music")
    await send_next_flow_track(callback, state, keywords)

@router.callback_query(F.data == "flow_stop", FlowStates.playing)
async def flow_stop(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("⏹ Flow остановлен")
    text = "🌑 **Добро пожаловать в LIMINAL**.\nМузыка на пороге состояний.\nВыбери действие ниже 👇"
    await callback.message.answer(text, reply_markup=get_main_menu_kb(), parse_mode="Markdown")