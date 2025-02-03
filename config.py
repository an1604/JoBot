import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Singleton configuration class to manage environment variables."""

    _instance = None  # Singleton instance

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_env_variables()
        return cls._instance

    def _load_env_variables(self):
        """Loads environment variables into the instance attributes."""
        self.LINKEDIN_USERNAME = os.getenv('LINKEDIN_USERNAME')
        self.LINKEDIN_PASSWORD = os.getenv('LINKEDIN_PASSWORD')
        self.LINKEDIN_TEMP_USERNAME = os.getenv('LINKEDIN_TEMP_USERNAME')
        self.LINKEDIN_TEMP_PASSWORD = os.getenv('LINKEDIN_TEMP_PASSWORD')
        self.mail_server = os.getenv('MAIL_SERVER')
        self.mail_username = os.getenv('MAIL_USERNAME')
        self.mail_password = os.getenv('MAIL_PASSWORD')
        self.mongo_host = os.getenv('MONGO_HOST', 'localhost')
        self.mongo_port = os.getenv('MONGO_PORT', '27017')
        self.telegram_bot_token = os.getenv("JOBOT_TOKEN")
        self.MY_EMAIL = os.getenv("MY_MAIL")
        self.MY_PASSWORD = os.getenv("MY_PASSWORD")
        self.mail_port = os.getenv('MAIL_PORT')
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
        self.LLM_TOOL_CALL_MODEL_NAME = os.getenv("LLM_TOOL_CALL_MODEL_NAME")
        self.TELEGRAM_CLIENT_APP_ID = os.getenv("TELEGRAM_CLIENT_APP_ID")
        self.TELEGRAM_CLIENT_APP_HASH = os.getenv("TELEGRAM_CLIENT_APP_HASH")
        self.phone_number = os.getenv("PHONE_NUMBER")


config = Config()
