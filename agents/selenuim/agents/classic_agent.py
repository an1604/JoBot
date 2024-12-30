"""
This is the base agent the all the agents inherit from.
"""
import logging
from selenium import webdriver
from selenium.common.exceptions import WebDriverException

from agents.file_manager import file_manager


class Agent(object):
    def __init__(self, urls, name):
        self.driver = None
        self.urls = urls
        self.name = name
        self.jobs_filepath = file_manager.get_jobs_filepath(name)

    def get_jobs(self):
        """Method to override in child classes"""
        raise NotImplementedError("Subclasses must implement this method")

    def initialize_driver(self):
        stop = 0
        while stop <= 5:
            try:
                logging.info("Initializing WebDriver.")
                self.driver = webdriver.Chrome()
                return
            except WebDriverException as e:
                logging.error(f"WebDriver initialization failed: {e}")
                stop += 1
