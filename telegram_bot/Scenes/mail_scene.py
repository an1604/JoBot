import pdb
from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.fsm.scene import Scene, on
from aiogram.types import Message

from agents.llm import PROMPTS
from mail.mail_manager import send_email
from traffic_agent.linkedin_traffic_agent import llm

mail_message = None


class MailScene(Scene, state="mail"):
    """
    This class represents a scene for managing email interactions.

    It inherits from the Scene class and is associated with the state "mail".
    It handles the logic and flow of managing emails.
    """

    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext, step: int | None = 0) -> Any:
        await message.answer(f"What is the mail address?")
        await state.update_data(step=step)

    @on.message()
    async def handle_message(self, message: Message, state: FSMContext):
        global mail_message

        user_data = await state.get_data()
        step = user_data['step'] + 1
        await state.update_data(step=step)

        user_response = message.text

        pdb.set_trace()
        if "email_address" not in user_data:
            email = message.text
            await state.update_data(email_address=email)
            await message.answer(f"Got it! The email address is: {email}")
            await self.send_email(message, state)
        elif 'send' in user_response.lower():
            send_email(email_receiver=user_data["email_address"], email_body=mail_message)
            await message.answer("Successfully send the message!")
        elif "edit" in user_response.lower():
            changed_message = user_response.split("edit:")[-1]
            send_email(email_receiver=user_data["email_address"], email_body=changed_message)
        else:

            mail_message = llm.invoke(
                PROMPTS.SEND_EMAIL_TEMPLATE.format(feedback=mail_message,
                                                   recipient=user_data["email_address"]))
            res = f"Here is the change after your feedback:\n\n{mail_message}\n\n."
            await message.answer(res)

    @staticmethod
    async def send_email(message: Message, state: FSMContext):
        user_data = await state.get_data()
        email = user_data.get("email_address", "unknown")
        res = f"Please provide an intro to the mail and the sender. I will generate a mail for you using the address: {email}"
        await message.answer(res)
