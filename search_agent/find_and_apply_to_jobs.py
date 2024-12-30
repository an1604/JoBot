"""
Find and apply to jobs.

@dev You need to add OPENAI_API_KEY to your environment variables.

Also, you have to install PyPDF2 to read PDF files: pip install PyPDF2
"""

import csv
import os
import pdb
import re
import sys
from pathlib import Path

from PyPDF2 import PdfReader

from browser_use.browser.browser import Browser, BrowserConfig

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from typing import List, Optional

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langchain_ollama import ChatOllama
from pydantic import BaseModel, SecretStr

from browser_use import ActionResult, Agent, Controller
from browser_use.browser.context import BrowserContext

load_dotenv()
import logging
from agents.file_manager import file_manager

logger = logging.getLogger(__name__)
# full screen mode
controller = Controller()
CV = file_manager.get_resume_filepath("pdf")
print(f"CV path: {CV}")


class Job(BaseModel):
    title: str
    link: str
    company: str
    fit_score: float
    location: Optional[str] = None
    salary: Optional[str] = None


@controller.action(
    'Save jobs to file - with a score how well it fits to my profile', param_model=Job
)
def save_jobs(job: Job):
    with open('jobs.csv', 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([job.title, job.company, job.link, job.salary, job.location])

    return 'Saved job to file'


@controller.action('Read jobs from file')
def read_jobs():
    with open('jobs.csv', 'r') as f:
        return f.read()


@controller.action('Read my cv for context to fill forms')
def read_cv(_format_="pdf"):
    # import pdb
    # pdb.set_trace()
    if _format_ == "pdf":
        pdf = PdfReader(CV)
        text = ''
        for page in pdf.pages:
            text += page.extract_text() or ''
        logger.info(f'Read cv with {len(text)} characters')
    elif _format_ == "txt":
        with open(CV, 'r') as f:
            text = f.read()
    return ActionResult(extracted_content=text, include_in_memory=True)


@controller.action(
    'Upload cv to element - call this function to upload if element is not found, try with different index of the same upload element',
    requires_browser=True,
)
async def upload_cv(index: int, browser: BrowserContext):
    path = str(CV.absolute())
    dom_el = await browser.get_dom_element_by_index(index)

    if dom_el is None:
        return ActionResult(error=f'No element found at index {index}')

    file_upload_dom_el = dom_el.get_file_upload_element()

    if file_upload_dom_el is None:
        logger.info(f'No file upload element found at index {index}')
        return ActionResult(error=f'No file upload element found at index {index}')

    file_upload_el = await browser.get_locate_element(file_upload_dom_el)

    if file_upload_el is None:
        logger.info(f'No file upload element found at index {index}')
        return ActionResult(error=f'No file upload element found at index {index}')

    try:
        await file_upload_el.set_input_files(path)
        msg = f'Successfully uploaded file to index {index}'
        logger.info(msg)
        return ActionResult(extracted_content=msg)
    except Exception as e:
        logger.debug(f'Error in set_input_files: {str(e)}')
        return ActionResult(error=f'Failed to upload file to index {index}')


# chrome_instance_path = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
chrome_instance_path = r"C:\Users\אביב\Desktop\chrome-win\chrome.exe"
browser = Browser(
    config=BrowserConfig(
        chrome_instance_path=chrome_instance_path,
        disable_security=True,
    )
)


async def main():
    # ground_task = (
    # 	'You are a professional job finder. '
    # 	'1. Read my cv with read_cv'
    # 	'2. Read the saved jobs file '
    # 	'3. start applying to the first link of Amazon '
    # 	'You can navigate through pages e.g. by scrolling '
    # 	'Make sure to be on the english version of the page'
    # )
    ground_task = (
        'You are a professional job finder. '
        '1. Read my cv with read_cv'
        '\n2. Apply to the job in this url: '
    )
    tasks = [
        ground_task + "https://emea-aligntech.icims.com/jobs/41727/login?_sp=2d0e6a26-193a-45a5-8bc9-33fc5de6e46f.1733991076459&_jsqid=undefined&iis=LinkedIn&_ga=2.39731046.491803844.1733991057-1945078860.1732623535&_gl=1*1gvojhx*_ga*MTk0NTA3ODg2MC4xNzMyNjIzNTM1*_ga_5Y2BYGL910*MTczMzk5MTA1Ny4yLjAuMTczMzk5MTA1Ny42MC4wLjA.&mobile=false&width=1070&height=500&bga=true&needsRedirect=false&jan1offset=120&jun1offset=180",
    ]
    # model = ChatOpenAI(
    #     model='gpt-4o',
    #     api_key=SecretStr(os.getenv('OPENAI_API_KEY', '')),
    # )
    model = ChatOllama(model='llama3-groq-tool-use',temperature=0)
    agents = []
    for task in tasks:
        agent = Agent(task=task, llm=model, controller=controller, browser=browser)
        agents.append(agent)

    await asyncio.gather(*[agent.run() for agent in agents])


if __name__ == '__main__':
    asyncio.run(main())
