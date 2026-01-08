from aiogram.fsm.state import State, StatesGroup

class OrderFlow(StatesGroup):
    waiting_photo = State()
    waiting_ref = State()
    waiting_comment = State()
    waiting_service = State()
