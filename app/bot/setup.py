from aiogram import Dispatcher


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    # Handlers will be registered in subsequent milestones
    return dp
