from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

router = Router()

def get_main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Fetch", callback_data="action_fetch")],
        [InlineKeyboardButton(text="🌊 Flow", callback_data="action_flow")],
        [InlineKeyboardButton(text="🎛 Playlists", callback_data="action_playlists")],
        [InlineKeyboardButton(text="⚙️ Settings", callback_data="action_settings")]
    ])

def get_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")]
    ])

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_name = message.from_user.full_name or "Путник"
    text = f"🌑 **Добро пожаловать в LIMINAL**, {user_name}.\nМузыка на пороге состояний.\nВыбери действие ниже 👇"
    await message.answer(text, reply_markup=get_main_menu_kb(), parse_mode="Markdown")

@router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_name = callback.from_user.full_name or "Путник"
    text = f"🌑 **Добро пожаловать в LIMINAL**, {user_name}.\nМузыка на пороге состояний.\nВыбери действие ниже 👇"
    await callback.message.edit_text(text, reply_markup=get_main_menu_kb(), parse_mode="Markdown")
    await callback.answer()