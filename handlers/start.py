from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

router = Router()


def get_main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔎 Fetch", callback_data="action_fetch"),
            InlineKeyboardButton(text=" Flow", callback_data="action_flow")
        ],
        [
            InlineKeyboardButton(text=" Playlists", callback_data="action_playlists"),
            InlineKeyboardButton(text="⚙️ Settings", callback_data="action_settings")
        ]
    ])


def get_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")]
    ])


@router.message(CommandStart())
async def cmd_start(message: Message):
    user_name = message.from_user.full_name or "Путник"
    
    text = (
        f" **Добро пожаловать в LIMINAL**, {user_name}.\n\n"
        f"Музыка на пороге состояний.\n"
        f"Поиск по всем платформам, умное радио и архив твоих вайбов.\n\n"
        f"Выбери действие ниже 👇"
    )
    
    await message.answer(text, reply_markup=get_main_menu_kb(), parse_mode="Markdown")



@router.callback_query(F.data.startswith("action_"))
async def handle_main_menu_buttons(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    
    if action == "fetch":
        from handlers.fetch import FetchStates
        
        await state.set_state(FetchStates.waiting_for_query)
        
        text = (
            " **Fetch: Режим поиска**\n\n"
            "Отправь мне:\n"
            "• Название трека (например, *Nightcall Kavinsky*)\n"
            "• Ссылку на Spotify, YouTube, SoundCloud\n"
            "• Ссылку на целый плейлист"
        )
        
        await callback.message.edit_text(
            text, 
            reply_markup=get_back_kb(), 
            parse_mode="Markdown"
        )
        await callback.answer()
        return  
    
    if action == "flow":
        text = (
            "🌊 **Flow**\n\nЛовим какую волну?\n\n"
            "🌧 Меланхолия\n"
            "☀️ Веселое\n"
            "⚡ Энергичное\n"
            "🌙 Ночное"
        )
    elif action == "playlists":
        text = "🎛 **Playlists**\n\nТвои подборки:\n\n➕ Создать новый плейлист"
    elif action == "settings":
        text = "⚙️ **Settings**\n\n🔊 Качество: 320 kbps\n🌐 Источник: SoundCloud"
    else:
        text = "Раздел в разработке..."

    await callback.message.edit_text(
        text, 
        reply_markup=get_back_kb(), 
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state:
        await state.clear()
    
    user_name = callback.from_user.full_name or "Путник"
    
    text = (
        f"🌑 **Добро пожаловать в LIMINAL**, {user_name}.\n\n"
        f"Музыка на пороге состояний.\n\n"
        f"Выбери действие ниже 👇"
    )
    
    await callback.message.edit_text(
        text, 
        reply_markup=get_main_menu_kb(), 
        parse_mode="Markdown"
    )
    await callback.answer()