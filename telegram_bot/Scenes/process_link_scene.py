from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.fsm.scene import Scene, on
from aiogram.types import Message

from traffic_agent.linkedin_traffic_agent import llm, LinkedinTrafficAgent, Connection

linkedin_crawler = LinkedinTrafficAgent()
generated_message = None


class ProcessLinkScene(Scene, state="process_link"):
    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext, step: int | None = 0) -> Any:
        # pdb.set_trace()

        await message.answer(f"Please provide a link to the Linkedin page of the target")
        await state.update_data(step=step)

    @on.message()
    async def handle_message(self, message: Message, state: FSMContext):
        global generated_message
        # pdb.set_trace()

        user_data = await state.get_data()
        step = user_data['step'] + 1
        await state.update_data(step=step)

        user_response = message.text

        if 'https' in user_response:
            if 'link' not in user_data:
                await state.update_data(link=user_response.strip())
                await message.answer(f"Got it! The link is: {user_response}")
                await self.extract_information_from_link(message, state, user_response.strip())
            else:
                await message.answer("You already provided a link as I seen so far...")
        else:
            if 'send' in user_response.lower() or 'yes' in user_response.lower():
                connection = Connection.from_dict(user_data['connection'])
                linkedin_crawler.send_message(connection, generated_message)
                await message.answer(f"Message sent to {connection.user_name}")
            else:
                connection = Connection.from_dict(user_data['connection'])
                generated_message = linkedin_crawler.generate_message(connection, user_response, use_llm=True)
                await message.answer(f"Here is the refinement after your feedback:\n\n {generated_message}")

    @staticmethod
    async def extract_information_from_link(message: Message, state: FSMContext, link):
        try:
            data = linkedin_crawler.process_link(link, use_temp_user=False)
            await state.update_data(connection=data.to_dict())
            await message.answer("The information extracted is:\n\n"
                                 f"\nName: {data.user_name}"
                                 f"\nDetails: {data.user_description}"
                                 f"\nMessage: {data.suggested_message}"
                                 f"\nLink:{data.link_to_profile}\n\n"
                                 f"\nWhat should I do next?")
        except Exception as e:
            await message.answer(f"Exception occur, info: {e}")
