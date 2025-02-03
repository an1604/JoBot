import pdb
from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.fsm.scene import Scene, on
from aiogram.types import Message

from agents.llm import PROMPTS
from mail.mail_manager import mail_manager
from traffic_agent.linkedin_traffic_agent import llm
from agents.file_manager import file_manager

mail_message = None


class MailScene(Scene, state="mail"):
    """
    This class represents a scene for managing email interactions.

    It inherits from the Scene class and is associated with the state "mail".
    It handles the logic and flow of managing emails.
    """

    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext, step: int | None = 0) -> Any:
        await message.answer(f"To explore emails, type one of the following:"
                             f"\n1) To create a new email message, type:\n\temail <email_address>"
                             f"\n2) To get updates, type:\n\tupdate <number of previous emails>")
        await state.update_data(step=step)

    @on.message()
    async def handle_message(self, message: Message, state: FSMContext):
        global mail_message
        user_data = await state.get_data()
        step = user_data['step'] + 1
        await state.update_data(step=step)

        user_response = message.text
        if user_response.startswith('email'):
            if "email_address" not in user_data:
                email = message.text.split('email')[-1]
                await state.update_data(email_address=email)
                await message.answer(f"Got it! The email address is: {email}")
                await self.send_email(message, state)
        elif user_response.startswith("update"):
            client_credentials = file_manager.get_path_from_mail_manager('client_secret.json')
            token_pickle_filepath = file_manager.get_path_from_mail_manager('token.pickle')
            num_of_prev_mails = int(user_response.split('update')[-1])
            emails_summary = mail_manager.getEmails(maxResults=num_of_prev_mails, format_='str',
                                                    client_credentials=client_credentials,
                                                    token_pickle_filepath=token_pickle_filepath)

            await message.answer(f"Here is the summary of the given mails:\n\n {emails_summary}")
        elif user_response.lower().startswith('send'):
            mail_manager.send_email(email_receiver=user_data["email_address"], email_body=mail_message)
            await state.clear()
            await message.answer("Successfully send the message!")

        elif user_response.lower().startswith('edit'):
            changed_message = user_response.split("edit:")[-1]
            mail_manager.send_email(email_receiver=user_data["email_address"], email_body=changed_message)
            await state.clear()
            await message.answer("Successfully send the message!")
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
