from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.fsm.scene import Scene, on
from aiogram.types import Message

from agents.selenuim.agents.linkdien_selen_agent import Linkedin_agent

agent = Linkedin_agent()


class ApplyJobsScene(Scene, state="apply"):
    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext, step: int | None = 0) -> Any:
        await message.answer(f"Are you sure that you want to run the job applier agent?")

    @on.message()
    async def handle_message(self, message: Message, state: FSMContext):
        user_response = message.text
        if "yes" in user_response.lower():
            agent.get_jobs(need_login=True, use_temp_profile=False)
            await message.answer("Agent starts running!")
        elif "stop" in user_response.lower():
            agent.stop()
            await message.answer("Agent stop running!")
        else:
            await message.answer("I have no answer for this.")
