import asyncio
import logging
import pdb
from os import getenv
from threading import Event
from typing import Any
from deep_translator import GoogleTranslator

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.scene import Scene, SceneRegistry, ScenesManager, on
from aiogram.fsm.storage.memory import SimpleEventIsolation
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup

from dotenv import load_dotenv

from agents.selenuim.agents.linkdien_selen_agent import Linkedin_agent

from telegram_bot.Scenes.easy_apply_scene import ApplyJobsScene
from telegram_bot.Scenes.process_link_scene import ProcessLinkScene
from telegram_bot.chatbot_models import User
from telegram_bot.Scenes.mail_scene import MailScene
from traffic_agent.linkedin_traffic_agent import LinkedinTrafficAgent, llm

load_dotenv()

translator_en_to_iw = GoogleTranslator(source='en', target='iw')
translator_iw_to_en = GoogleTranslator(source='iw', target='en')

TOKEN = getenv("JOBOT_TOKEN")
linkedin_crawler = LinkedinTrafficAgent()
linkedin_agent = Linkedin_agent()
current_company = 'microsoft'

posts = False
keyword = None

users = {}


def get_or_create_user(user):
    # Checks if the user exists, if not, it will add the user to the dictionary.
    user_id = user.id
    if user_id not in users.keys():
        users[user_id] = User(user_id=user_id,
                              user_name=user.username if user.username else f"{user.first_name} {user.last_name}".strip())
    return users[user_id]


class CrawlState(StatesGroup):
    waiting_for_url = State()
    waiting_for_company_name = State()


def handle_routes(bot_router):
    @bot_router.message(Command("start"))
    async def command_start(message: Message, scenes: ScenesManager):
        user = get_or_create_user(user=message.from_user)
        await scenes.close()
        if user:
            await message.answer(
                "Hi! It's JoBot. To start to crawl linkedin, type company name (/company_name) and then run (/run).")

    @bot_router.message(Command("help"))
    async def help_command(message: Message) -> None:
        await message.answer("/run - run the linkedin crawl.\n")

    @bot_router.message(Command('keyword'))
    async def keyword_command(message: Message, state: FSMContext):
        global posts, keyword

        user = get_or_create_user(user=message.from_user)
        if user:
            keyword = message.text.split('/keyword')[-1]
            posts = True
            await message.answer(f"Keyword {keyword} is saved!\n"
                                 f"You can now run the crawl with /run.")

    @bot_router.message(Command("company_name"))
    async def company_name_command(message: Message, state: FSMContext) -> None:
        """
        Ask the user for the company name and set FSM state.
        """
        logging.info(
            f"Received command /company_name from user {message.from_user.id} ({message.from_user.username})"
        )
        user = get_or_create_user(user=message.from_user)
        if user:
            await message.answer("Please enter the company name to proceed:")
            await state.set_state(CrawlState.waiting_for_company_name)

    @bot_router.message(CrawlState.waiting_for_company_name)
    async def get_company_name(message: Message, state: FSMContext) -> None:
        """
        Capture the company_name and ask the user to run the crawl.
        """
        global current_company

        company_name = message.text.strip()
        if not company_name:
            await message.answer("The company name cannot be empty. Please provide a valid company name.")
            return
        current_company = company_name
        await state.update_data(company_name=company_name)
        await message.answer(f"Company name '{company_name}' received. You can now run the crawl with /run.")
        await state.clear()


def create_dispatcher(attack_router):
    # Event isolation is needed to correctly handle fast user responses
    dispatcher = Dispatcher(
        events_isolation=SimpleEventIsolation(),
    )
    dispatcher.include_router(attack_router)

    # To use scenes, you should create a SceneRegistry and register your scenes there
    scene_registry = SceneRegistry(dispatcher)
    # ... and then register a scene in the registry
    # by default, Scene will be mounted to the router that passed to the SceneRegistry,
    # but you can specify the router explicitly using the `router` argument
    scene_registry.add(CrawlScene)
    scene_registry.add(MailScene)
    scene_registry.add(ProcessLinkScene)
    scene_registry.add(ApplyJobsScene)
    return dispatcher


def get_colleague(colleagues=None, current_index=0):
    return colleagues[current_index] if colleagues is not None else None


class CrawlScene(Scene, state="run"):
    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext, step: int | None = 0) -> Any:
        """
        Triggered when the user enters the CrawlScene.
        """
        global current_company, posts, keyword

        if not step:
            data = await state.get_data()
            if posts and keyword is not None:
                posts_summary = linkedin_crawler.crawl_posts_by_keywords(keywords=keyword, use_tmp_user=True,
                                                                         need_login=True,
                                                                         get_summary=True)
                await message.answer(f"Posts form the given keyword {keyword}: \n\n{posts_summary}")
                keyword = None
                posts = False
            else:
                company_name = current_company if current_company else data.get("company_name")
                await message.answer(f"Searching for hiring colleagues at '{company_name}'. Please wait...")
                colleagues = list(linkedin_crawler.get_hiring_colleagues(company_name))
                print(f"Found {len(colleagues)} colleagues.")
                await state.update_data(colleagues=colleagues, current_index=0)
                await self.process_next_colleague(message, state)

    async def process_next_colleague(self, message: Message, state: FSMContext, from_posts=False) -> None:
        """
        Processes the next colleague by asking the user for confirmation.
        """
        global posts

        current_index = None
        data = await state.get_data()
        colleagues = data.get("colleagues")
        current_index = data.get("current_index", 0)

        if not colleagues:
            logging.error("Colleagues list is empty or None.")
            await message.answer("No colleagues found to process. Please restart the crawl process.")
            await state.clear()
            return

        if current_index < 0 or current_index >= len(colleagues):
            logging.error(f"Invalid current_index: {current_index}. Colleagues length: {len(colleagues)}")
            await message.answer("An error occurred while processing the colleague list. Please try again.")
            await state.clear()
            return

        colleague = colleagues[current_index]

        if colleague is None:
            logging.warning(f"Skipping None colleague at index {current_index}.")
            await state.update_data(current_index=current_index + 1)
            await self.process_next_colleague(message, state)
            return

        try:
            generated_message = linkedin_crawler.generate_message(colleague)
            msg = (f"Index: {current_index if current_index else "None"}\n\n"
                   f"Colleague: {colleague.user_name}\n\n"
                   f"Details: {colleague.user_description}\n\n"
                   f"Linkedin: {colleague.link_to_profile}\n"
                   f"Message: {generated_message}\n\n"
                   "\nDo you want to send this message? Reply with 'yes' or provide feedback."
                   "\nIn addition, you can edit the message by yourself, by typing 'edit:' before the change.") \
                if not from_posts else (
                f"Index: {current_index if current_index else "None"}\n\n"
                f"Name: {posts[current_index]._name}\n\n"
                f"Details: {posts[current_index]._content}\n\n"
                f"Linkedin: {posts[current_index].link}\n"
            )
            await state.update_data(generated_message=generated_message)
            await message.answer(msg)
        except Exception as e:
            logging.error(f"Error while generating or sending message: {e}")
            await message.answer("An error occurred while generating the message. Please try again.")
            await state.clear()

    @on.message()
    async def handle_confirmation(self, message: Message, state: FSMContext) -> None:
        """
        Handles user confirmation for sending the message, with feedback support.
        """
        data = await state.get_data()
        current_index = data.get("current_index", 0)
        colleagues = data.get("colleagues")
        generated_message = data.get("generated_message")

        user_response = message.text.strip()
        if user_response.lower() == "yes":
            colleague = get_colleague(colleagues, current_index)
            linkedin_crawler.send_message(colleague, generated_message)
            await message.answer(f"Message sent to {colleague.user_name}.")
            await state.update_data(current_index=current_index + 1)
            await self.process_next_colleague(message, state)
        else:
            colleague = get_colleague(colleagues, current_index)
            feedback = message.text.strip()
            if feedback.lower() == "skip":
                await message.answer("Skipping this colleague. Moving to the next one.")
                await state.update_data(current_index=current_index + 1)
                await self.process_next_colleague(message, state)
            elif "edit" in feedback.lower():
                changed_message = feedback.split("edit:")[-1]
                linkedin_crawler.send_message(colleague, changed_message)
                await message.answer(f"Message sent to {colleague.user_name}.")
                await self.process_next_colleague(message, state)
            else:
                generated_message = linkedin_crawler.generate_message(colleague, feedback, use_llm=True)
                await state.update_data(generated_message=generated_message)
                await message.answer(
                    f"Here is the refinement after your feedback:\n\n{generated_message}\n\n What should I do next?")


class ChatBot(object):
    def __init__(self):
        self.bot = None
        self.dispatcher = None

        self.attack_router = Router(name=__name__)
        handle_routes(self.attack_router)
        self.shutdown_event = Event()

    async def start(self):
        # Add handler that initializes the scene
        self.attack_router.message.register(CrawlScene.as_handler(), Command("run"))
        self.attack_router.message.register(MailScene.as_handler(), Command("mail"))
        self.attack_router.message.register(ProcessLinkScene.as_handler(), Command("process_link"))
        self.attack_router.message.register(ApplyJobsScene.as_handler(), Command("apply"))
        self.dispatcher = create_dispatcher(self.attack_router)

        self.bot = Bot(token=TOKEN)
        await self.dispatcher.start_polling(self.bot)

    def stop(self):
        self.shutdown_event.set()
        self.dispatcher.shutdown()


async def main():
    chatbot = ChatBot()
    try:
        await chatbot.start()
    except KeyboardInterrupt:
        logging.info("Shutting down bot...")
        chatbot.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
