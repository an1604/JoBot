"""
Simple try of the agent.

@dev You need to add OPENAI_API_KEY to your environment variables.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio

from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from browser_use import Agent

# video: https://preview.screen.studio/share/70xBqZyN
llm = ChatOpenAI(model='gpt-4o')
# llm = ChatOllama(model="llama3.1:latest")
agent = Agent(
    task='Go to amazon.com, search for laptop, sort by best rating, and give me the price of the first result',
    llm=llm,
)


async def main():
    await agent.run()


asyncio.run(main())
