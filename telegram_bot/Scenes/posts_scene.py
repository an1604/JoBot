import re
from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.fsm.scene import Scene, on
from aiogram.types import Message

from traffic_agent.linkedin_traffic_agent import agent


class PostsScene(Scene, state='posts'):

    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext) -> Any:
        await message.answer(
            "What posts do you want me to crawl? (keyword/group)\n"
            "\nNOTE: If you want to crawl by keyword, please type:\n\t keyword <keyword>."
            "\nIf you want to crawl from a group, type: \n\t group <group_url>,  Leave blank for the default group."
        )
        await state.update_data(step=0, posts=None)

    @on.message()
    async def handle_message(self, message: Message, state: FSMContext):
        user_data = await state.get_data()
        user_response = message.text.strip().lower()

        if user_response.startswith('keyword'):
            keyword = user_response.removeprefix('keyword').strip()
            if not keyword:
                await message.answer("Please provide a keyword after 'keyword'.")
                return
            await self.crawl_by_keywords(message, state, keyword)

        elif user_response.startswith('group'):
            url = user_response.removeprefix('group').strip() or None
            await self.crawl_from_group(message, state, url)

        else:
            await message.answer("Invalid input. Please type 'keyword <keyword>' or 'group <group_url>'.")

    async def crawl_by_keywords(self, message: Message, state: FSMContext, keyword: str):
        await message.answer(f"Starting to crawl posts with the keyword: {keyword}...")
        try:
            posts = agent.crawl_posts_by_keywords(keywords=keyword, use_tmp_user=True,
                                                  need_login=True,
                                                  get_summary=True)
            await self.process_posts(message, state, posts)
        except Exception as e:
            await message.answer(f"An error occurred while crawling by keyword: {e}")

    async def crawl_from_group(self, message: Message, state: FSMContext, url: str | None):
        await message.answer(f"Starting to crawl posts from the group: {url or 'default group'}...")
        try:
            if url is not None:
                posts = agent.crawl_posts_from_group(url=url, get_summary=True)
            else:
                posts = agent.crawl_posts_from_group(get_summary=True)

            await self.process_posts(message, state, posts)
        except Exception as e:
            await message.answer(f"An error occurred while crawling from group: {e}")

    async def process_posts(self, message: Message, state: FSMContext, posts: Any):
        if not posts:
            await message.answer("No posts were found based on your input.")
            return

        await state.update_data(posts=posts)
        await message.answer(f"Here are the posts: \n\n{posts}")
