import json
import os
import pdb
import re
import time
from urllib.parse import urlencode, quote

from deep_translator import GoogleTranslator

import agents.selenuim.agents.linkedin.linkedinFunctions as lf
from agents.Server.db import get_db
from langchain_community.llms import Ollama
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium import webdriver
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import logging

from selenium.webdriver.support.wait import WebDriverWait
import random

from agents.file_manager import file_manager

from agents.llm import PROMPTS
from traffic_agent.posts import Post
from config import config

llm = Ollama(model=config.LLM_MODEL_NAME)


class Connection:
    def __init__(self, name, link_to_profile, user_description, suggested_message=None, company_name='none',
                 generate_new_message=True):
        self.user_name = name
        self.link_to_profile = link_to_profile
        self.user_description = user_description
        self.company_name = company_name
        self.messages_dirpath = file_manager.get_path_from_traffic_agent()
        self.prompt_for_llm = file_manager.get_prompt_filepath(filename='prompt_for_generate_message.txt')
        self.messages_list = self.get_messages_list()

        self.feedback = ('Look for its current company, and use it as the company name, and look for its current role'
                         'and use it in the message too.'
                         f'\n {self.user_description}')
        self.suggested_message = None
        if generate_new_message and not suggested_message:
            self.suggested_message = self.get_suggested_message()
        else:
            self.suggested_message = suggested_message

    @staticmethod
    def save_connection_to_db(connection):
        db = get_db()
        connections_collection = db['connections']
        connections_collection.insert_one(connection.to_dict())

    def to_dict(self):
        return {
            "user_name": self.user_name,
            "link_to_profile": self.link_to_profile,
            "user_description": self.user_description,
            "suggested_message": self.suggested_message if not self.suggested_message is None else 'None',
            'company_name': self.company_name
        }

    def to_json(self):
        return json.dumps(self.to_dict())

    @staticmethod
    def from_dict(connection_dict):
        """
        Creates a Connection object from a dictionary.

        Args:
            connection_dict (dict): A dictionary containing connection details.

        Returns:
            Connection: An instance of the Connection class.
        """
        # Check for the presence of keys
        is_suggested_message = "suggested_message" in connection_dict
        is_company_name = "company_name" in connection_dict

        # Get required fields with a fallback for missing keys
        user_name = connection_dict.get("user_name", "Unknown User")
        link_to_profile = connection_dict.get("link_to_profile", "#")
        user_description = connection_dict.get("user_description", "No description available.")

        suggested_message = connection_dict.get("suggested_message", None) if is_suggested_message else None
        company_name = connection_dict.get("company_name", None) if is_company_name else None
        connection = Connection(name=user_name, link_to_profile=link_to_profile, user_description=user_description,
                                generate_new_message=not suggested_message)
        if suggested_message:
            connection.suggested_message = suggested_message
        if company_name:
            connection.company_name = company_name
        return connection

    @staticmethod
    def from_json(connection_json):
        return Connection.from_dict(json.loads(connection_json))

    def __eq__(self, other):
        return self.link_to_profile == other.link_to_profile

    def __hash__(self):
        return hash((self.user_name, self.link_to_profile, self.user_description))

    def get_suggested_message(self):
        if self.suggested_message is None:
            global llm

            message = self.pick_message().format(name=self.user_name,
                                                 company=f'[add the current company {self.user_name} works at]')
            with open(self.prompt_for_llm, 'r') as f:
                data = f.read()
                prompt = data.format(info=self.to_dict(),
                                     message=message, feedback=self.feedback)
                return llm.invoke(prompt)
        return self.suggested_message

    def get_messages_list(self):
        messages = set()
        for filename in os.listdir(self.messages_dirpath):
            if filename.startswith("message") and filename.endswith(".txt"):
                with open(os.path.join(self.messages_dirpath, filename), 'r') as f:
                    message = f.read()
                    messages.add(message)
        return list(messages)

    def pick_message(self):
        import random
        return random.choice(self.messages_list)


class LinkedinTrafficAgent:
    def __init__(self, url='https://www.linkedin.com/feed/'):
        self.last_connection_from_process_url = None
        self.current_company = None
        self.url = url
        self.driver = None

        self.colleagues_dirpath = file_manager.get_path_from_traffic_agent('colleagues_details')
        self.connections_dirpath = file_manager.get_path_from_traffic_agent('connections_details')
        self.companies_objs_for_colleagues = self.get_all_companies_as_objects(target='colleagues')
        self.companies_objs_for_connections = self.get_all_companies_as_objects(target='connections')
        self.all_company_names = self.get_company_names()

        self.messages_dirpath = file_manager.get_path_from_traffic_agent()
        self.messages_stack = self.get_messages()
        self.prompt_for_llm = file_manager.get_prompt_filepath(filename='prompt_for_generate_message.txt')
        self.last_message_generated = 'No last message generated yet.'

    def login_to_linkedin(self, use_tmp_user):
        try:
            if self.driver is None:
                self.initialize_driver()
            user_name, password = self.get_user_info(use_tmp_user)
            self.driver.get('https://www.linkedin.com/login')
            logging.info("Navigated to LinkedIn login page")
            try:
                logging.info("Attempting to log in")
                self.driver.find_element(By.ID, 'username').send_keys(user_name)
                self.driver.find_element(By.ID, 'password').send_keys(password)
                self.driver.find_element(By.CSS_SELECTOR, '.login__form_action_container button').click()
                logging.info("Login successful")
            except NoSuchElementException as e:
                logging.error(f"Login elements not found: {e}")
                self.driver.quit()
                exit()
        except Exception as e:
            print(f"Exception occur: {e}")
            self.driver.quit()
            exit()

    def close_messages_overlay(self):
        stop = 0
        while stop <= 5:
            try:
                wait = WebDriverWait(self.driver, 10)

                dropdown_button = wait.until(EC.presence_of_element_located((
                    By.XPATH,
                    "//button[@aria-label='Open messenger dropdown menu']"
                )))

                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                                           dropdown_button)
                dropdown_button.click()

                dropdown_container = wait.until(EC.visibility_of_element_located((
                    By.XPATH,
                    "//div[contains(@class, 'msg-overlay-bubble-header__dropdown-container')]"
                )))
                if dropdown_container.is_displayed():
                    print("Dropdown menu successfully expanded.")
                    return True

            except Exception as e:
                print(f"Error interacting with the dropdown button: {e}")
                stop += 1

        print("Failed to interact with the dropdown button after multiple attempts.")
        return False

    def search_company(self, company_name, max_connections=10, use_temp_profile=False):
        potential_connections = None
        if self.need_to_run(company_name, max_connections):
            self.initialize_driver(use_temp_profile)
            logging.info("Navigated to LinkedIn feed page")
            try:
                potential_connections = self.get_potential_connections(max_connections=max_connections,
                                                                       company_name=company_name)

                self.companies_objs_for_connections[company_name] = (potential_connections, max_connections)
                filename = self.get_company_filename(company_name)
                self.save_details(filename=filename,
                                  connections=potential_connections)
                self.save_connections_to_db(company_name=company_name, connections_=list(potential_connections))
                self.driver.quit()
                return potential_connections
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                self.driver.quit()
                return potential_connections
        else:
            return self.companies_objs_for_connections[company_name][0]

    def get_searchbar_and_search(self, company_name):
        search_bar_xpath = """//*[@id="global-nav-typeahead"]/input"""
        search_bar = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, search_bar_xpath))
        )
        self.driver.execute_script("arguments[0].value = arguments[1];", search_bar, company_name)
        search_bar.send_keys(Keys.RETURN)

    def get_potential_connections(self, max_connections, company_name):
        potential_connections = {}
        try:
            pdb.set_trace()

            self.get_searchbar_and_search(company_name)  # Collect the search bar, and search for the company
            time.sleep(3)
            link = self.get_see_all_link()
            self.driver.get(link)
            stop = 0
            while len(potential_connections) <= max_connections and stop <= 10:
                li_items = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//ul[@role='list']//li"))
                )
                try:
                    for li_item in li_items:
                        if not 'don’t forget to verify before reaching out' in li_item.text:
                            connection = self.process_connection(li_item, company_name)
                            if connection:
                                potential_connections[connection.user_name.lower()] = connection

                    # Handle the next page button
                    if not self.get_next_page():
                        break
                except Exception as e:
                    logging.error(f"Error processing potential connection: {e}")
                    stop += 1
                    continue
        except Exception as e:
            logging.error(f"Error fetching connections: {e}")
        return potential_connections

    @staticmethod
    def save_details(filename, connections):
        if isinstance(connections, dict):
            connections = list(connections.values())

        with open(filename, "w", encoding="utf-8") as f:
            for connection in connections:
                if not isinstance(connection, Connection):
                    connection = connection[-1]
                f.write(connection.to_json() + "\n")
            print(f"Details saved to {filename}")

    def get_all_companies_as_objects(self, target):
        # Get all companies from files, to avoid extra computation.
        companies = {}
        try:
            dir_path = self.get_correct_dirpath(FROM=target)

            for file_name in os.listdir(dir_path):
                file_path = os.path.join(dir_path, file_name)
                if os.path.isfile(file_path) and file_name.endswith('.json'):
                    logging.info(f"Processing file: {file_name}")

                    company_name = self.extract_company_name(file_name)
                    connections_ = self.process_file(company_name, file_path)

                    companies[company_name] = (connections_, len(connections_))
                    logging.info(f"Stored company name: {company_name} in the dictionary!")
                else:
                    logging.warning(f"Could not extract company name from: {file_name}")


        except Exception as e:
            logging.error(f"An error occurred while processing files: {e}")

        return companies

    @staticmethod
    def process_file(company_name, file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            if company_name:
                data = [json.loads(line) for line in file]
                connections_ = []
                for entry in data:
                    if isinstance(entry, dict):
                        connection = Connection.from_dict(entry)
                    else:
                        connection = Connection.from_json(entry)
                    connections_.append(connection)
            return list(set(connections_))  # Remove duplications

    @staticmethod
    def extract_company_name(content):
        return content.split(".json")[0]

    def need_to_run(self, company_name, max_connections=10, target="potential_connection"):
        try:
            if 'connection' in target:
                return ((not company_name in self.companies_objs_for_connections.keys())
                        and (
                                abs(self.companies_objs_for_connections[company_name][1] - max_connections) > 5
                        ))
            elif 'colleagues' in target:
                return not f'{company_name}_colleagues' in self.companies_objs_for_colleagues.keys()
        except KeyError:
            return True

    def get_see_all_link(self):
        # Getting the `see all` button, and press it to load all potential connections
        see_all_link_connections = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH,
                                        "//div[contains(@class, 'search-results__cluster-bottom-banner')]/a[contains(text(), 'See all people results')]"
                                        ))
        )
        link = see_all_link_connections.get_attribute("href")
        return link

    @staticmethod
    def process_connection(li_item, company_name):
        global llm

        stop_ = 0
        while stop_ <= 5:
            try:
                a_tag = li_item.find_element(By.XPATH,
                                             ".//a[contains(@href, 'linkedin.com/in') or contains(@href, 'linkedin.com')]")
                text = li_item.text
                user_name = text.split("\n")[0].strip()
                user_description = llm.invoke(
                    f"Please give me a 2-3 lines of description about the following user {user_name}:\n{text}"
                )
                link_to_profile = a_tag.get_attribute("href")
                connection = Connection(name=user_name, link_to_profile=link_to_profile,
                                        user_description=user_description,
                                        company_name=company_name, generate_new_message=True)
                return connection
            except:
                stop_ += 1
        return None

    def get_next_page(self, next_btn_xpath="//button[contains(@class, 'artdeco-pagination__button--next')]"):
        try:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            next_button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable(
                    (By.XPATH, next_btn_xpath))
            )
            next_button.click()
            logging.info("Clicked on the 'Next' button")
            return True
        except TimeoutException:
            logging.info("No 'Next' button found. End of pagination.")
            return False

    def get_hiring_colleagues(self, company_name, get_page=True, use_temp_profile=False,
                              rand_hiring=False, url_from_input=None):
        self.current_company = company_name
        if self.need_to_run(company_name, target="potential_colleagues"):
            print(f"self.current_company = {company_name}.")
            if not self.driver:
                self.initialize_driver(use_temp_profile)
            if url_from_input is not None:
                self.url = url_from_input
            elif "no company" in company_name.lower():
                self.url = self.get_random_hiring_url()
                rand_hiring = True

            if self.url not in self.driver.current_url:
                # TODO: THIS IS THE CURRENT IF STATEMENT --> if self.url not in self.driver.current_url and get_page:
                self.driver.get(self.url)

            if not rand_hiring:  # rand_hiring=True is getting directly to the target page
                # Search for the company again, and target the hiring people now.
                self.get_searchbar_and_search(company_name)  # Collect the search bar, and search for the company
                time.sleep(3)  # Allow time for the search to process
                link = self.get_see_all_link()
                self.driver.get(link)

            # Get the target page that contains all hiring colleagues.
            colleagues = {}
            if self.get_hiring_page(get_page):
                colleagues = self.get_all_colleagues(company_name, rand_hiring)
                if len(colleagues) > 0:
                    filepath = os.path.join(file_manager.get_path_from_traffic_agent('colleagues_details'),
                                            f'{company_name}_colleagues.json')
                    self.save_details(filepath, colleagues)
                return [colleague[-1] for colleague in colleagues]
        return self.companies_objs_for_colleagues[f'{company_name}_colleagues'][0]

    def get_hiring_page(self, get_page=True):
        if get_page:
            try:
                # Get the actively hiring button to filter the options
                wait = WebDriverWait(self.driver, 10)
                actively_hiring_button = wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//button[contains(@class, 'artdeco-pill') "
                                   "and contains(@class, 'search-reusables__filter-pill-button') "
                                   "and contains(@aria-label, 'Actively hiring')]")
                    )
                )
                actively_hiring_button.click()
                time.sleep(2)  # Ensure the page loads the options

                options = wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//ul[contains(@class, 'search-reusables__collection-values-container')]")
                    )
                )
                logging.info("Locating 'Any job title' option...")
                li_item = options.find_element(By.XPATH, ".//li[.//span[text()='Any job title']]")

                label = li_item.find_element(By.XPATH, ".//label")
                label.click()
                time.sleep(1)  # Allow time for the label click action to propagate

                # Click on the 'Show Results' button
                show_results_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Show results']]"))
                )
                show_results_button.click()
                logging.info("'Show Results' button clicked successfully.")
                return True
            except Exception as e:
                logging.error(f"An unexpected error occurred: {e}")
                return False
        return True

    def handle_connect_modal(self, connection):
        try:
            logging.info("Checking for modal...")
            wait = WebDriverWait(self.driver, 5)
            add_note_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Add a note']]"))
            )
            add_note_button.click()
            time.sleep(1)  # Delay to allow modal to stabilize
            if self.add_note_and_send(connection, process_add_note=False):
                return True
        except Exception as e:
            logging.error(f"An error occurred while handling the modal: {e}")
            return False

    def add_note_and_send(self, connection, response=None, process_add_note=True,
                          text_area_classname="//textarea[@id='custom-message']"):
        try:
            logging.info("Adding a note to the connection request...")
            wait = WebDriverWait(self.driver, 10)

            if process_add_note:
                add_note_btn = wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//button[@aria-label='Add a note']")
                ))
                # Scroll to the button and click it
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                                           add_note_btn)
                add_note_btn.click()
                time.sleep(1)

            note_textarea = wait.until(
                EC.visibility_of_element_located((By.XPATH, text_area_classname))
            )
            if not response:
                response = self.generate_message(connection)

            note_textarea.clear()
            self.driver.execute_script("arguments[0].innerHTML = '';", note_textarea)

            note_textarea.send_keys(response)

            send_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Send']]"))
            )
            send_button.click()
            logging.info("Connection request sent successfully.")
            time.sleep(1)  # Delay before returning to ensure all actions are completed
            return True
        except TimeoutException:
            logging.warning("Textarea or Send button not found. Skipping this colleague.")
        except Exception as e:
            logging.error(f"An error occurred while adding a note and sending the request: {e}")

    def send_message(self, connection: Connection, message, use_temp_profile=False,
                     get_more_hiring=False):
        """
        Sends a message to a LinkedIn connection using Selenium and logs the process.

        Args:
            message (str): The message to send to the connection.
            connection (Connection): The connection data for the LinkedIn user.

        Returns:
            bool: True if the message was sent successfully, False otherwise.
            :param get_more_hiring:
        """
        try:
            link_to_profile = connection.link_to_profile
            if not link_to_profile:
                logging.error("Missing link_to_profile in connection data.")
                return False

            logging.info(f"Navigating to profile: {link_to_profile}")
            if not self.driver:
                self.initialize_driver(use_temp_profile)
            self.driver.get(link_to_profile)
            time.sleep(3)

            done = False
            if self.connect_from_connection_page():
                time.sleep(1)
                self.add_note_and_send(connection, message)
                done = True
            elif self.send_direct_message():
                self.add_note_and_send(connection, message,
                                       process_add_note=False)
                done = True
            elif self.introduce_myself(message):
                self.add_note_and_send(connection, message, process_add_note=False,
                                       text_area_classname="//div[@role='textbox' and contains(@class, 'msg-form__contenteditable')]")
                done = True
            if get_more_hiring:
                more_hiring = self.get_more_hiring_profiles_from_page(write_to_a_file=True)
        except WebDriverException as e:
            logging.error(f"WebDriverException occurred: {e}")
            return False
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            return False

    def generate_message(self, connection,
                         feedback='no feedback so far, generate the message according to the requirements!',
                         use_llm=False):
        global llm
        response = ''
        # TODO: FIX THE BUG IN THE PROCESS_URL IN CHATBOT SERVER!!
        # pdb.set_trace()
        if connection is None:
            connection = self.last_connection_from_process_url
        first_name = connection.user_name.split()[0]

        if not use_llm:
            message = self.get_rand_message(first_name, self.current_company)
            return message

        if self.last_message_generated == 'No last message generated yet.':
            if connection.suggested_message is None:
                message = self.messages_stack[0].format(name=first_name, company=self.current_company)
            else:
                message = connection.suggested_message
        else:
            message = self.last_message_generated

        if connection:
            prompt = open(self.prompt_for_llm, 'r').read().format(info=connection.to_dict(),
                                                                  message=message, feedback=feedback)
            response = llm.invoke(prompt)

            while 'Here is' in response:
                response = llm.invoke(prompt)

            # TODO: COMMENT IT TO SEE IF THE TELEGRAM BOT CAN MAKE IT
            # user_accept = input(f"Please confirm this message to send to the colleague: {connection.user_name}\n"
            #                     f"{response}\n"
            #                     f"Write yes/no")
        # Strip any leading or trailing quotes, introductions, or explanations
        response = re.sub(r'^.*?"', '', response).strip()  # Remove everything before the first quote
        response = re.sub(r'"$', '', response)  # Remove the trailing quote if it exists

        self.last_message_generated = response
        return response

    def get_messages(self):
        messages = set()
        for filename in os.listdir(self.messages_dirpath):
            if filename.endswith(".txt") and filename.startswith("message"):
                file_path = os.path.join(self.messages_dirpath, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        data = file.read()
                        messages.add(data)
                except UnicodeDecodeError as e:
                    logging.error(f"UnicodeDecodeError in file {file_path}: {e}")
        return list(messages)

    def initialize_driver(self, use_tmp_user=False, need_login=True):
        self.driver = webdriver.Chrome()
        if need_login:
            self.login_to_linkedin(use_tmp_user)

    @staticmethod
    def make_connection():
        choice = random.choice([1, 2])
        return choice == 1

    def get_all_colleagues(self, company_name, rand_hiring, PAGE_IDX_THRESHOLD=3):
        if rand_hiring:
            PAGE_IDX_THRESHOLD = 111
        colleagues = {}
        wait = WebDriverWait(self.driver, 10)
        stop = 0
        page_idx = 0

        while stop <= 10 and page_idx <= PAGE_IDX_THRESHOLD:
            try:
                time.sleep(3)
                hiring_colleagues = wait.until(
                    EC.presence_of_all_elements_located((By.XPATH, "//ul[@role='list']//li"))
                )
                for colleague in hiring_colleagues:
                    try:
                        connection = self.process_connection(colleague, company_name)
                        if connection is not None:
                            # TODO: FIX THIS connection_in_db FUCNTION!!
                            # if connection_in_db(connection):
                            colleagues[connection.user_name.lower()] = connection

                            print(
                                f"\ncolleague: {connection.user_name} added to the set, total size: {len(colleagues)}")
                    except Exception as e:
                        logging.warning(f"Error processing colleague: {e}")
                self.get_next_page("//button[@aria-label='Next']")
                page_idx += 1
                print(f"Page idx: {page_idx}, with {len(colleagues)} colleagues in the set. ")
            except Exception as e:
                logging.warning(f"Error during pagination or colleague processing: {e}")
                stop += 1
        return list(colleagues.items())

    def locate_and_send_message(self, message):
        """
        Locate the text area element using both general XPath and Shadow DOM handling, and send a message.

        Args:
            message (str): The message to send to the located text area.

        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
        try:
            wait = WebDriverWait(self.driver, 10)
            text_area = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH,
                     "//div[@role='textbox' and @contenteditable='true' and contains(@aria-label, 'Write a message')]")
                )
            )
            print("Text area found using general XPath.")
        except TimeoutException:
            print("Text area not found using general XPath. Trying Shadow DOM...")
            try:
                text_area = self.driver.execute_script("""
                    return document.querySelector('div[contenteditable="true"][role="textbox"]');
                """)
                if text_area:
                    print("Text area found using Shadow DOM.")
                else:
                    print("Text area not found using Shadow DOM.")
                    return False
            except Exception as e:
                print(f"An error occurred while locating the text area via Shadow DOM: {e}")
                return False

        try:
            self.driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
                                       text_area)

            text_area.send_keys(message)
            print(f"Message sent: {message}")
            return True
        except Exception as e:
            print(f"An error occurred while interacting with the text area: {e}")
            return False

    def close_chat(self):
        stop = 0
        while stop <= 5:
            try:
                wait = WebDriverWait(self.driver, 10)
                close_button = wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH,
                         "//button[contains(@class, 'msg-overlay-bubble-header__control') and .//span[contains(text(), 'Close your conversation')]]")
                    )
                )
                close_button.click()
                print("Successfully clicked the close button.")
            except Exception as e:
                stop += 1

    @staticmethod
    def get_company_names():
        companies = set()
        try:
            companies_filepath = file_manager.get_path_from_companies("all_companies.json")
            with open(companies_filepath, 'r') as file:
                for line in file:
                    # Step 1: convert the line to json object
                    json_line = json.loads(line)
                    company_name = json_line['company_name']
                    companies.add(company_name)
        except Exception as e:
            logging.error(f"An error occurred while processing files: {e}")
        return companies

    def stop(self):
        self.driver.quit()

    @staticmethod
    def get_company_filename(company_name):
        dir_path = file_manager.get_path_from_traffic_agent('connections_details')
        filename = file_manager.get_filename_by_company(company_name, dir_path)
        return filename

    def connect_and_send_message(self, colleague, connection):
        stop = 0
        while stop <= 5:
            try:
                connect_button = self.get_connect_or_message_btn(colleague)
                if connect_button:
                    connect_button.click()
                self.handle_connect_modal(connection)
                time.sleep(1)  # Small delay between interactions
            except Exception as e:
                stop += 1

    @staticmethod
    def get_connect_or_message_btn(colleague, type_='Connect'):
        stop = 5
        while stop <= 5:
            try:
                btn = WebDriverWait(colleague, 5).until(
                    EC.element_to_be_clickable((By.XPATH, f".//button[.//span[text()='{type_}']]"))
                )
                return btn
            except Exception as e:
                stop += 1
        return None

    def get_rand_message(self, name, company):
        import random
        message = random.choice(self.messages_stack)
        return message.format(name=name, company=company)

    def connect_from_connection_page(self):
        stop = 0
        while stop <= 5:
            try:
                if lf.findButtonFromType(self.driver, btn_type="Connect"):
                    return True
            except:
                pass

            try:
                if lf.findButtonFromType(self.driver, btn_type="More"):
                    time.sleep(2)
                    if lf.findButtonFromType(self.driver, btn_type="Connect"):
                        return True
                else:
                    dropdown_container = WebDriverWait(self.driver, 10).until(
                        EC.visibility_of_element_located(
                            (By.XPATH, "//div[contains(@class, 'artdeco-dropdown__content')]"))
                    )
                    connect_btn = WebDriverWait(dropdown_container, 10).until(
                        EC.element_to_be_clickable((
                            By.XPATH,
                            ".//div[contains(@aria-label, 'Invite') and contains(@class, 'artdeco-dropdown__item')]//span[contains(text(), 'Connect')]"
                        ))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", connect_btn)
                    connect_btn.click()
                    return True
                stop += 1
            except:
                stop += 1

        print("Failed to click the 'Connect' button after multiple attempts.")
        return False

    def click_connect_button(self):
        stop = 0

        while stop <= 5:
            try:
                # self.close_messages_overlay()
                time.sleep(1)
                wait = WebDriverWait(self.driver, 10)
                connect_div = wait.until(EC.presence_of_element_located((
                    By.XPATH,
                    "//div[contains(@aria-label, 'Invite') and .//span[text()='Connect']]"
                )))
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                                           connect_div)
                connect_div.click()
                return True
            except Exception as e:
                print(f"Error clicking the 'Connect' button: {e}")
                stop += 1
        return False

    def introduce_myself(self, message):
        stop = 0
        while stop <= 5:
            try:
                if not lf.findButtonFromType(self.driver, btn_type="Introduce myself"):
                    try:
                        wait = WebDriverWait(self.driver, 10)
                        introduce_button = wait.until(EC.presence_of_element_located((
                            By.XPATH,
                            "//button[.//span[text()='Introduce myself']]"
                        )))
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                            introduce_button)
                        introduce_button.click()
                        print("Clicked the 'Introduce myself' button successfully.")
                        return True
                    except:
                        stop += 1
                else:
                    return True
            except Exception as e:
                print(f"Error clicking the 'Introduce myself' button: {e}")
                stop += 1
        return False

    @staticmethod
    def get_user_info(use_tmp_user):
        if use_tmp_user:
            return config.LINKEDIN_TEMP_USERNAME, config.LINKEDIN_TEMP_PASSWORD
        return config.LINKEDIN_USERNAME, config.LINKEDIN_PASSWORD

    @staticmethod
    def save_connections_to_db(company_name, connections_):
        """
        Saves connections to the MongoDB collection, ensuring that the company_name is unique.

        Args:
            company_name (str): The unique key for the connections.
            connections_ (list): A list of Connection objects to save.
        """
        db = get_db()
        connections_collection = db['connections_collection']

        connections_collection.create_index("company_name", unique=True)
        connections_as_dict = [connection.to_dict() for connection in connections_]
        document = {
            "company_name": company_name,
            "connections": connections_as_dict
        }
        try:
            connections_collection.update_one(
                {"company_name": company_name},  # Filter by company_name
                {"$set": document},  # Update the document with new data
                upsert=True  # Insert if it doesn't exist
            )
            print(f"Connections for {company_name} saved successfully.")
        except Exception as e:
            print(f"Error saving connections to database: {e}")

    def send_direct_message(self):
        try:
            if lf.findButtonFromType(self.driver, btn_type="Message"):
                header = self.driver.find_element(By.XPATH, "//h2[contains(text(), 'Get more InMail credits')]")
                return not header  # it means true.
            return False
        except:
            return False

    @staticmethod
    def get_random_hiring_url():
        return random.choice([
            "https://www.linkedin.com/search/results/people/?keywords=hiring%20manager&origin=CLUSTER_EXPANSION&sid=bD*",
            "https://www.linkedin.com/search/results/people/?keywords=hiring&origin=SWITCH_SEARCH_VERTICAL&sid=W*S"])

    def get_more_hiring_profiles_from_page(self, write_to_a_file=False):
        stop = 0
        while stop <= 3:
            try:
                more_hiring = set()
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//li[contains(@class, 'artdeco-list__item')]"))
                )
                li_elements = self.driver.find_elements(By.XPATH, "//li[contains(@class, 'artdeco-list__item')]")
                for li_element in li_elements:
                    profile_link_element = WebDriverWait(li_element, 10).until(
                        EC.presence_of_element_located((By.XPATH,
                                                        "//a[contains(@class, 'optional-action-target-wrapper') and contains(@href, 'linkedin.com/in')]"))
                    )
                    user_name = profile_link_element.text
                    profile_link = profile_link_element.get_attribute("href")
                    user_description = li_element.text
                    connection = Connection(name=user_name, link_to_profile=profile_link,
                                            user_description=user_description)
                    more_hiring.add(connection)

                if write_to_a_file:
                    self.write_objects_to_file(objects=more_hiring, is_more_hiring=True)
                return more_hiring
            except Exception as e:
                stop += 1
        return []

    @staticmethod
    def write_objects_to_file(objects, is_more_hiring=True, file_path=None):
        if is_more_hiring:
            traffic_agent_file_path = file_manager.get_path_from_traffic_agent('colleagues_details')
            file_path = os.path.join(traffic_agent_file_path, "more_hiring.json")

        with open(file_path, 'a') as file:
            for connection in objects:
                file.write(json.dumps(connection.to_dict()) + "\n")

    def process_link(self, url_, use_temp_user=False):
        if self.driver is None:
            self.initialize_driver(use_temp_user)
        xpath = "//div[contains(@class, 'relative')]//a[contains(@href, '/overlay/about-this-profile/')]"
        stop = 0
        while stop <= 4:
            try:
                self.driver.get(url_)
                time.sleep(4)
                wait = WebDriverWait(self.driver, 10)
                user_info_container = wait.until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                user_name = user_info_container.find_element(By.TAG_NAME, 'h1').text
                # user_desc = user_info_container.text
                desc = lf.getContent(html=self.driver.page_source, container_type="section", name='about')
                user_desc = llm.invoke(PROMPTS.REFINE_USER_DESCRIPTION.format(user_name=user_name, desc=desc))
                connection = Connection(name=user_name, link_to_profile=url_, user_description=user_desc)
                self.last_connection_from_process_url = connection
                return connection
            except:
                stop += 1
        return None

    def remove_connections(self, connections, FROM='colleagues'):
        from agents.Server.db import drop_connection_from_db

        for connection in connections:
            drop_connection_from_db(connection)

        dirpath = self.get_correct_dirpath(FROM)
        if not connections:
            return  # If no connections, exit early

        company_name = connections[0].company_name
        filepath = os.path.join(dirpath, f'{company_name}_{FROM}.json')
        ids_to_remove = {conn.name for conn in connections}
        try:
            with open(filepath, 'r') as file:
                lines = file.readlines()
            updated_lines = []
            for line in lines:
                try:
                    entry = json.loads(line.strip())  # Parse each line as JSON
                    if entry.get("name") not in ids_to_remove:
                        updated_lines.append(line)
                except json.JSONDecodeError:
                    continue
            with open(filepath, 'w') as file:
                file.writelines(updated_lines)
        except FileNotFoundError:
            print(f"File {filepath} not found.")
        except Exception as e:
            print(f"An error occurred: {e}")

    def get_correct_dirpath(self, FROM):
        if 'connections' in FROM:
            return self.connections_dirpath
        return self.colleagues_dirpath

    @staticmethod
    def generate_linkedin_search_url(keywords):
        base_url = "https://www.linkedin.com/search/results/content/"
        query_params = {
            "keywords": keywords,
            "origin": "SWITCH_SEARCH_VERTICAL",
            "sid": "fU:"
        }
        encoded_params = urlencode(query_params, quote_via=quote)
        search_url = f"{base_url}?{encoded_params}"
        return search_url

    def crawl_posts_by_keywords(self, keywords, need_login=True, use_tmp_user=True,
                                get_summary=False):
        keyword_url = self.generate_linkedin_search_url(keywords)
        if need_login:
            self.initialize_driver(use_tmp_user=use_tmp_user)
        self.driver.get(keyword_url)
        time.sleep(3)
        dynamic_class_name = input("What is the <ul> classname?")
        ul_xpath_query = f"//ul[contains(@class, '{dynamic_class_name}') and @role='list']"

        posts = self.get_posts_content(ul_xpath_query)
        posts_dirpath = file_manager.get_path_from_traffic_agent(dirname="posts")
        file_path = os.path.join(posts_dirpath, f"posts_{keywords}")
        self.write_objects_to_file(objects=posts, is_more_hiring=False, file_path=file_path)

        self.stop()

        if get_summary:
            return llm.invoke(
                PROMPTS.SUMMARIZE_POSTS_TEMPLATE.format(posts=[json.dumps(post.to_dict()) for post in posts]))
        return list(posts)

    def get_posts_content(self, ul_xpath_query, TOTAL_POSTS=13):
        posts_content = set()
        stop = 0
        # pdb.set_trace()
        while stop <= 3 and len(posts_content) < TOTAL_POSTS:
            try:
                self.scroll_down()
                posts_list = self.get_posts_li_items(ul_xpath_query)
                if posts_list is None:
                    raise Exception("posts_list is None")

                for li in posts_list:
                    if "Feed post" in li.text:
                        try:
                            # pdb.set_trace()
                            link = li.find_element(By.TAG_NAME, "a").get_attribute("href")
                            post = self.create_post_obj(text=li.text, links=link)
                            if post:
                                posts_content.add(post)
                            print(f"post: {post.to_dict()} in set, total size: {len(posts_content)}")
                        except:
                            continue
            except:
                stop += 1
        return posts_content

    def scroll_down(self, TOTAL_SCROLLS=1):
        scroll_idx = 0
        while scroll_idx < TOTAL_SCROLLS:
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                scroll_idx += 1
            except:
                scroll_idx += 1

    def get_posts_li_items(self, ul_xpath_query):
        stop = 0
        while stop < 3:
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, ul_xpath_query)))

                posts_list = []
                for ul in self.driver.find_elements(By.XPATH, ul_xpath_query):
                    try:
                        items = ul.find_elements(By.TAG_NAME, "li")
                        posts_list.extend(items)
                    except:
                        continue
                return posts_list
            except:
                stop += 1
        return None

    @staticmethod
    def read_posts(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return [Post.from_dict(item) for item in data]
            else:
                return data

    def crawl_posts_from_group(self, url="https://www.linkedin.com/groups/8879236/", need_login=True,
                               use_temp_user=True, get_summary=False):
        if need_login:
            self.initialize_driver(use_tmp_user=use_temp_user)
        self.driver.get(url)
        time.sleep(2)

        last_len = 0
        posts = []
        max_iterations = 15
        iterations = 0

        POSTS_XPATH = "//div[contains(@class, 'AgVfPiNz')]"
        show_more_btn_xpath = "//button[contains(@class, 'artdeco-button')]"

        while iterations < max_iterations:
            iterations += 1
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            posts = self.driver.find_elements(By.XPATH, POSTS_XPATH)

            if len(posts) == last_len:
                if not self.load_more_posts(xpath=show_more_btn_xpath):
                    break
            last_len = len(posts)
        print(f"Total posts collected: {len(posts)}")

        posts_objs = []
        for post in posts:
            text = post.text
            self.driver.execute_script("arguments[0].scrollIntoView(true);", post)
            links = self.get_links_from_post(post)
            post_obj = self.create_post_obj(text=text, links=links)
            if post_obj:
                posts_objs.append(post_obj)

        posts_dirpath = file_manager.get_path_from_traffic_agent(dirname="posts")
        file_path = os.path.join(posts_dirpath, "posts_from_group.json")
        self.write_objects_to_file(objects=posts_objs, is_more_hiring=False, file_path=file_path)
        if get_summary:
            posts_dict = [json.dumps(post.to_dict()) for post in posts_objs]
            return llm.invoke(
                PROMPTS.SUMMARIZE_POSTS_TEMPLATE.format(posts=posts_dict))
        return posts_objs

    @staticmethod
    def create_post_obj(text, links=None):
        try:
            translator = GoogleTranslator(source='iw', target='en')
            if len(text.split()) > 2:
                prompt = PROMPTS.SUMMARIZE_POST_CONTENT_TEMPLATE.format(
                    content=translator.translate(text))
                json_res = llm.invoke(prompt)
                llm_res = json.loads(json_res)
                if links is not None and len(links) > 0:
                    llm_res['link'] = links
                post = Post.from_dict(llm_res)
                return post
            return None
        except:
            return None

    def load_more_posts(self, xpath):
        try:
            show_more_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            self.driver.execute_script("arguments[0].scrollIntoView(true);", show_more_btn)
            show_more_btn.click()
            time.sleep(2)
            return True
        except Exception as e:
            print(f"No 'Show More' button or error clicking: {e}")
            return False

    @staticmethod
    def get_links_from_post(post):
        links = set()
        url_pattern = re.compile(
            r"(https?://[^\s]+|www\.[^\s]+|\b[a-zA-Z0-9.-]+\.(com|org|net|edu|gov|co|il)\b)"
        )

        # 1. Extract links from post-text
        for match in url_pattern.findall(post.text):
            links.add(match)

        # 2. Extract links from <span> elements
        spans = post.find_elements(By.TAG_NAME, 'span')
        for span in spans:
            span_text = span.text.strip()
            if span_text and url_pattern.search(span_text):
                links.add(span_text)

        # 3. Extract links from <article> within the parent <div>
        try:
            parent_div = post.find_element(By.XPATH, "./ancestor::div[1]")
            article = parent_div.find_element(By.TAG_NAME, "article")
            for a in article.find_elements(By.TAG_NAME, "a"):
                href = a.get_attribute('href')
                if href:
                    links.add(href)
        except:
            pass

        # 4. Extract direct <a> tags from the post
        try:
            for a in post.find_elements(By.TAG_NAME, "a"):
                href = a.get_attribute("href")
                if href:
                    links.add(href)
        except:
            pass

        return list(links)


agent = LinkedinTrafficAgent()
if __name__ == '__main__':
    connections_ = agent.search_company("nvidia", 5,
                                        use_temp_profile=True)
