import os
import pdb
from email.message import EmailMessage
import ssl
import smtplib
from dotenv import load_dotenv
from agents.file_manager import file_manager

load_dotenv()

SENDER = os.getenv('MAIL_USERNAME')


def send_email(email_receiver, email_body, display_name='Aviv Nataf', email_subject="Aviv Nataf resume",
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
    email_sender = SENDER
    email_password = os.getenv('MAIL_PASSWORD')

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
    with smtplib.SMTP_SSL(os.getenv('MAIL_SERVER'), 465, context=context) as smtp:
        smtp.login(email_sender, email_password)
        smtp.sendmail(email_sender, email_receiver, em.as_string())
