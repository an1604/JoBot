import asyncio
import json
import os
import logging

from langchain_ollama import ChatOllama
from telethon import TelegramClient, events, errors
from config import config
from mail.mail_manager import mail_manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

stop = False
llm = ChatOllama(config.LLM_MODEL_NAME)


def check_content(message):
    global llm

    prompt = """
    Analyze the following message and determine if it is related to a job application. 
    Extract and return the following information in JSON format:

    - **job_topic**: The title or main topic of the job mentioned in the message (e.g., "Software Engineer", "Data Analyst"). If no job is found, return `null`.
    - **application_url**: The URL for applying to the job (if available). If no URL is found, return `null`.

    **Response Format:**
    ```json
    {{
      "job_topic": "Software Engineer",
      "application_url": "https://company.com/apply"
    }}
    ```
    If the message **does not contain a job application**, return:
    ```json
    {{
      "job_topic": null,
      "application_url": null
    }}
    ```

    **Message to analyze:**
    \"\"\"{message}\"\"\"
    """

    response = llm.invoke(prompt.format(message=message))
    return response


def generate_message(param):
    pass


class Client(object):
    def __init__(self, app_id, app_hash, phone_number):
        logging.info(f"Client.__init__: Initializing client with phone number {phone_number}")
        self.app_id = app_id
        self.app_hash = app_hash
        self.phone_number = phone_number

        self.loop = None
        self.make_event_loop()
        self.message_queue = asyncio.Queue()

        self.client = TelegramClient('session_name', self.app_id, self.app_hash)
        self.initialize_client()

    def handle_routes(self, client):
        logging.info(f"Client.handle_routes: Handling routes for client {client}")

        @client.on(events.NewMessage(incoming=True))
        async def handle_new_incoming_message(event):
            message = event.message.message
            sender = await event.get_sender()
            chat = await event.get_chat()
            logging.info(
                f"📩 Incoming message from [{sender.username or sender.first_name}] in [{chat.id}]: {message}")

            await self.message_queue.put((sender.id, message))

        @client.on(events.NewMessage(outgoing=True))
        async def handle_new_outgoing_message(event):
            message = event.message.message
            sender = await event.get_sender()
            chat = await event.get_chat()
            logging.info(
                f"📩 Outgoing message from [{sender.username or sender.first_name}] in [{chat.id}]: {message}")

            await self.message_queue.put((sender.id, message))

    import json

    async def process_queue(self):
        message_flag = False

        while True:
            sender_id, message = await self.message_queue.get()
            logging.info(f"📤 Processing message from {sender_id}: {message}")

            json_response = check_content(message)

            try:
                response_data = json.loads(json_response)

                job_topic = response_data.get("job_topic")
                application_url = response_data.get("application_url")

                if job_topic and application_url:  # Job detected with application link
                    response_text = (
                        f"🔹 **Job Detected**: {job_topic}\n"
                        f"🔗 **Apply Here**: {application_url}"
                    )
                    message_flag = True

                elif job_topic:  # Job detected but no URL
                    message_flag = True
                    response_text = f"🔹 **Job Detected**: {job_topic}\n🚫 No application link found."

                if message_flag:
                    # TODO: YOU CAN ALSO SEND EMAIL USING THE mail_manager object too, JUST UNCOMMENT THIS NEXT LINE
                    # mail_manager.send_email(config.MY_EMAIL, response_text, email_subject="Job alert!")
                    await self.send_message(receiver=config.phone_number, message=response_text)
                    message_flag = False
            except json.JSONDecodeError:
                logging.error("❌ Failed to parse JSON response from LLM.")
            self.message_queue.task_done()

    def initialize_client(self):
        logging.info("Client.initialize_client: Initializing client.")
        self.handle_routes(self.client)

        self.loop.create_task(self.run_client())
        self.loop.create_task(self.process_queue())

        logging.info("Client.initialize_client: Added run_client to the loop.")

    async def run_client(self):
        logging.info("Client.run_client: Running client...")
        try:
            await self.client.connect()
            await self.client.start(phone=self.phone_number)
            logging.info('Client.run_client: Client is running...')
            await self.client.run_until_disconnected()
        except errors.AuthKeyUnregisteredError:
            logging.error("Client.run_client: Authorization key not found or invalid. Re-authenticating...")
            await self.authenticate_client()
            await self.run_client()
        except Exception as e:
            logging.error(f"Client.run_client: An error occurred: {e}")
            await self.client.disconnect()

    async def send_message(self, receiver, message):
        logging.info(f"Client.send_message: Sending message to {receiver}")
        try:
            await self.client.connect()
            self.handle_routes(self.client)
            await self.client.send_message(receiver, message)
            logging.info(f'Client.send_message: Message sent: {message}')
        except errors.AuthKeyUnregisteredError:
            logging.error("Client.send_message: Authorization key not found or invalid. Re-authenticating...")
            await self.authenticate_client()
            await self.send_message(receiver, message)

    async def authenticate_client(self):
        logging.info("Client.authenticate_client: Authenticating client.")
        await self.client.send_code_request(self.phone_number)
        code = input('Enter the code you received: ')
        await self.client.sign_in(self.phone_number, code)

    def make_event_loop(self):
        logging.info("Client.make_event_loop: Creating event loop.")
        try:
            self.loop = asyncio.get_event_loop()
            asyncio.set_event_loop(self.loop)
        except RuntimeError as e:
            logging.error(f"Client.make_event_loop: RuntimeError encountered: {e}")
            if str(e).startswith('There is no current event loop in thread'):
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                logging.info("Client.make_event_loop: New event loop created.")
            else:
                raise


if __name__ == '__main__':

    tgram_client = Client(config.TELEGRAM_CLIENT_APP_ID, config.TELEGRAM_CLIENT_APP_HASH
                          , config.phone_number)

    try:
        logging.info("Client is running. Press Ctrl+C to stop.")
        tgram_client.loop.run_forever()  # Keeps the event loop running
    except KeyboardInterrupt:
        logging.info("Shutting down client...")
        tgram_client.loop.run_until_complete(tgram_client.client.disconnect())  # Properly disconnect
