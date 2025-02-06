from aiogram.fsm.state import State, StatesGroup


class ImageProcessing(StatesGroup):
    """States for the image processing workflow."""

    selecting_action = State()
    selecting_size = State()
    processing = State()
