from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.fsm.scene import Scene, on
from aiogram.types import Message

from agents.selenuim.agents.linkdien_selen_agent import Linkedin_agent

agent = Linkedin_agent()


class ApplyJobsScene(Scene, state="apply"):
    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext, step: int | None = 0) -> Any:
        await message.answer("What kind of jobs do you want me to fetch and apply?"
                             "\nPlease type:\n"
                             "1) link <insert_link>- to scrape a specific link for jobs (LinkedIn).\n"
                             "2) title <insert_title_name> - to scrape a specific job title (Junior software developer)"
                             "3) default - will scrape the default job page from LinkedIn.")

    @on.message()
    async def handle_message(self, message: Message, state: FSMContext):
        user_response = message.text
        in_process = False
        if user_response.startswith('link'):
            link = user_response.split('link')[-1]
            agent.process_url(apply=True, url=link, init_driver=True)
            in_process = True
        elif user_response.startswith("title"):
            title = user_response.split("title")[-1]
            agent.scrape_specific_job(use_temp_profile=False, job_title=title, apply=True)
            in_process = True
        elif user_response.startswith("default"):
            agent.get_jobs(use_temp_profile=False, apply=True)
            in_process = True
        else:
            if "yes" in user_response.lower():
                agent.get_jobs(need_login=True, use_temp_profile=False)
                await message.answer("Agent starts running!")
            elif "stop" in user_response.lower():
                agent.stop()
                await message.answer("Agent stop running!")
            else:
                await message.answer("I have no answer for this.")
        if in_process:
            await message.answer("Successfully done processing task!")
