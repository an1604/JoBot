import os
from email.message import EmailMessage
import ssl
import smtplib

from langchain_ollama import ChatOllama

from agents.file_manager import file_manager

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os.path
import base64
from bs4 import BeautifulSoup
from config import config

SENDER = config.mail_username

# Define the SCOPES. If modifying it, delete the token.pickle file.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
llm = ChatOllama(model=config.LLM_MODEL_NAME)


class Email:
    def __init__(self, subject, sender, body):
        self.subject = subject
        self.sender = sender
        self.body = None

        self.process_body(body)

    def __str__(self):
        return (f"Subject: {self.subject}\n"
                f"Sender: {self.sender}\n"
                f"Body: {self.body}")

    def process_body(self, body):
        global llm
        self.body = llm.invoke(f"Summarize this email content in 1-2 rows maximum\n"
                               f"Content: \n{body}\n"
                               f"\nDo not include any introduction, explanation, or additional text in the response.").content


class MailManager:
    def __init__(self):
        self.sender = SENDER
        self.scopes = SCOPES
        self.password = config.mail_password

    def send_email(self, email_receiver, email_body, display_name='Aviv Nataf', email_subject="Aviv Nataf resume",
                   from_email=SENDER,
                   attachments_filepath=file_manager.get_resume_filepath(format_="pdf")):
        """
        Send an email with optional file attachments.

        :param email_receiver: Recipient's email address
        :param email_body: Body of the email
        :param display_name: Sender's display name
        :param email_subject: Subject of the email
        :param from_email: Sender's email address (default provided)
        :param attachments_filepath: List of file paths to attach to the email
        """
        em = EmailMessage()
        if from_email:
            em['from'] = f"{display_name} <{SENDER}>"
        else:
            em['from'] = f"{display_name} <{SENDER}>"

        em['to'] = email_receiver
        em['subject'] = email_subject
        em.set_content(email_body)

        if attachments_filepath:
            try:
                with open(attachments_filepath, 'rb') as file:
                    file_data = file.read()
                    file_name = os.path.basename(attachments_filepath)
                    em.add_attachment(file_data, maintype='application', subtype='octet-stream', filename=file_name)
            except Exception as e:
                print(f"Failed to attach file {attachments_filepath}: {e}")

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(config.mail_server, 465, context=context) as smtp:
            smtp.login(self.sender, self.password)
            smtp.sendmail(self.sender, email_receiver, em.as_string())

    def getEmails(self, maxResults=20, format_='list', client_credentials=None, token_pickle_filepath=None):
        subject = 'None'
        sender = 'None'
        creds = None

        # Token file for storing access tokens
        token_pickle_filepath = token_pickle_filepath if token_pickle_filepath is not None else 'token.pickle'
        if os.path.exists(token_pickle_filepath):
            with open(token_pickle_filepath, 'rb') as token:
                creds = pickle.load(token)

        # If credentials are not available or invalid, prompt the user
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                client_credentials = client_credentials if client_credentials is not None else 'client_secret.json'
                flow = InstalledAppFlow.from_client_secrets_file(
                    client_credentials, scopes=SCOPES,
                )
                creds = flow.run_local_server(port=5002)

            # Save the credentials for next use
            with open(token_pickle_filepath, 'wb') as token:
                pickle.dump(creds, token)

        # Connect to the Gmail API
        service = build('gmail', 'v1', credentials=creds)

        # Request messages from the inbox
        result = service.users().messages().list(
            userId='me',
            maxResults=maxResults,
            q='label:inbox'  # Filter to only inbox emails
        ).execute()
        messages = result.get('messages', [])

        emails = []
        for msg in messages:
            txt = service.users().messages().get(userId='me', id=msg['id']).execute()
            try:
                payload = txt['payload']
                headers = payload['headers']

                # Extract Subject and Sender from headers
                for d in headers:
                    if d['name'] == 'Subject':
                        subject = d['value']
                    if d['name'] == 'From':
                        sender = d['value']

                # Decode the body of the message
                parts = payload.get('parts', [])
                body = ""
                if parts:
                    data = parts[0]['body']['data']
                    data = data.replace("-", "+").replace("_", "/")
                    decoded_data = base64.b64decode(data)
                    soup = BeautifulSoup(decoded_data, "lxml")
                    body = soup.body.get_text(strip=True) if soup.body else ""

                emails.append(Email(subject=subject, sender=sender, body=body))
            except Exception as e:
                print(f"Failed to process email {msg['id']}: {e}")

        # Return emails in the requested format
        if format_ == 'list':
            return emails
        summary = self.get_emails_summary(emails)
        print(summary)
        return summary

    @staticmethod
    def get_emails_summary(emails):
        return "\n\n".join(f"{i + 1}) {str(mail)}" for i, mail in enumerate(emails))


mail_manager = MailManager()
