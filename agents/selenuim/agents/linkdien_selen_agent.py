import logging
import os
import random
import re
import time
from langchain_community.llms import Ollama

from selenium import webdriver
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

from agents.job import Job
from agents.llm import llm_with_tools, PROMPTS
from agents.selenuim.agents.classic_agent import Agent

import requests
from agents.file_manager import file_manager
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

LINKEDIN_USERNAME = os.getenv("LINKEDIN_USERNAME")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
LINKEDIN_TEMP_USERNAME = os.getenv("LINKEDIN_TEMP_USERNAME")
LINKEDIN_TEMP_PASSWORD = os.getenv("LINKEDIN_TEMP_PASSWORD")


class Linkedin_agent(Agent):
    def __init__(self, urls=None, name="linkedin_jobs"):
        self.llm = Ollama(model="llama3.1")

        if not urls:
            urls = ['https://www.linkedin.com/jobs/',
                    'https://www.linkedin.com/jobs/collections/top-choice/?currentJobId=4042255671']
        super().__init__(urls, name)
        logging.info("Starting LinkedIn Job Scraper")
        self.driver = webdriver.Chrome()
        logging.info("WebDriver initialized")

        self.first_call_to_scrollable_div = True
        self.scrollable_div_classname = None

    def get_external_jobs_and_auto_apply(self, need_login=True):
        from agents.Server.db import get_jobs_from_db

        if self.driver is None or need_login:
            self.initialize_driver()
            self.login_to_linkedin(use_temp_profile=True)

        jobs_from_db = get_jobs_from_db(jobs_source="linkedin_jobs")
        jobs = [Job(**job) for job in jobs_from_db]
        jobs_count = 0
        jobs_set = set()
        while jobs_count <= 10:
            job_choice = self.get_rand_job(jobs, jobs_set)
            if job_choice:
                if self.apply_to_external_website(job_choice):
                    print("Job probably applied, sleep for 2 min before moving on")
                    time.sleep(120)
                    jobs_count += 1
                    print(f"Current jobs probably applied: {jobs_count}")

    def apply_to_external_website(self, job_choice):
        import agents.selenuim.agents.linkedin.linkedinFunctions as lf
        self.driver.get(job_choice.source)
        time.sleep(3)
        if lf.findButtonFromType(self.driver, btn_type="Apply"):
            time.sleep(5)
            url = self.driver.current_url

            payload = {
                "data_extraction_goal": None,
                "error_code_mapping": None,
                "extracted_information_schema": None,
                "navigation_goal": (
                    "Fill out the job application form and apply for the job. Fill out any public "
                    "burden questions if they appear in the form. Your goal is complete when the "
                    "page says you've successfully applied for the job. Terminate if you are unable "
                    "to use successfully.\n"
                    "When agreeing to the privacy policy, ensure it is done directly on the form without "
                    "navigating away to the privacy policy page.\n"
                ),
                "navigation_payload": {
                    "name": "Aviv Nataf",
                    "email": "nataf12386@gmail.com",
                    "phone": "0522464648",
                    "resume_url": "https://www.dropbox.com/scl/fi/x0idrg04ixsedqfp5wgv3/aviv_nataf_resume.pdf",
                    "cover_letter": "Generate a compelling cover letter for me",
                    "Gender": "Male",
                    "Linkedin_profile_url": "https://www.linkedin.com/in/aviv-nataf-757aa1247/",
                    "current_gpa": "86",
                    "school_option": "Other",
                    "school_name": "The college of management",
                    "expected_graduation_date": "March 2025",
                    "are_you_a_student": "yes",
                    "salary_expectations": "10000"
                },
                "proxy_location": "RESIDENTIAL",
                "totp_identifier": None,
                "totp_verification_url": None,
                "webhook_callback_url": None,
            }

            headers = {
                "Content-Type": "application/json"
            }
            response = requests.post(url, json=payload, headers=headers)
            return response.status_code == 200
        return False

    def get_next_page_button(self, page_index,
                             pagination_ul_xpath="//ul[contains(@class, 'artdeco-pagination__pages')]"):
        stop = 0
        while stop <= 4:
            try:
                pagination_ul = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, pagination_ul_xpath))
                )
                pagination_li = pagination_ul.find_elements(By.TAG_NAME, "li")
                load_more_pages = None
                for li in pagination_li:
                    try:
                        if '..' in li.text:
                            load_more_pages = li.find_element(By.TAG_NAME, "button")
                        if int(li.text) == page_index + 1:
                            return li.find_element(By.TAG_NAME, "button")
                    except:
                        stop += 1
                        continue
                if load_more_pages:
                    load_more_pages.click()
            except:
                return None

    def process_url(self, url, get_url=True, apply=True, pagination_xpath=None, init_driver=False):
        from agents.Server.db import add_job_to_job_collection
        if init_driver:
            self.initialize_driver()
            self.login_to_linkedin(use_temp_profile=False)
        stop = 0
        jobs_list = {}
        if get_url:
            self.driver.get(url)
        page_index = 1
        while stop < 10:
            try:
                scrollable_div = self.get_scrollable_div()
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", scrollable_div)
                if pagination_xpath:
                    load_more_job_btn = self.get_next_page_button(page_index,
                                                                  pagination_ul_xpath=pagination_xpath)
                else:
                    load_more_job_btn = self.get_next_page_button(page_index)

                logging.info("Fetching job listings")
                job_opportunities = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//li[@data-occludable-job-id]"))
                )
                if len(job_opportunities) > 0:
                    logging.info(f"Found {len(job_opportunities)} opportunities during scraping.")

                for i, job_card in enumerate(job_opportunities):
                    print(f"Process the {i}-th job.")
                    job_obj = self.process_job_card(job_card)
                    if apply:
                        _, is_easy_apply = self.apply_and_save_job(job_card, job_obj)
                        if is_easy_apply:
                            self.handle_done_popup()
                            if job_obj:
                                self.save_job_to_pending_jobs_collection(job_obj)
                    if job_obj:
                        print("Job created")
                        job_obj.set_job_element(job_card)
                        key = job_obj.job_title.title() + job_obj.company.lower()
                        if not key in jobs_list.keys():
                            Job.write_job_to_file(job_obj.to_dict(), self.jobs_filepath)
                        else:
                            jobs_list[key] = job_obj
                            add_job_to_job_collection(job_obj)

                if load_more_job_btn:
                    logging.info("Clicking 'Load more jobs' button")
                    load_more_job_btn.click()
                else:
                    stop += 1
                page_index += 1
            except Exception as e:
                logging.error(f"Unexpected exception occurred: {e}")
                stop += 1
                continue
        return

    def process_jobs_in_page(self, url_):
        stop = 0
        job_cards_set = set()
        while stop <= 10:
            try:
                # Scrolling down to the end of the page, to load to job cards dynamically
                self.scroll_page(FIND_SECTION=True)
                current_url = url_
                job_cards = self.get_job_cards(current_url)
                job_cards_objects = [self.make_hashable(card) for card in job_cards]
                for i in range(len(job_cards)):
                    try:
                        job_card = job_cards[i]
                        job_card_obj = job_cards_objects[i]
                        if not job_card_obj in job_cards_set:
                            job_cards_set.add(job_card)
                            self.driver.execute_script("arguments[0].scrollIntoView();", job_card)
                            job_obj = self.process_job_card(job_card)
                            current_url, easy_apply = self.apply_and_save_job(job_card, job_obj)
                            if easy_apply:
                                time.sleep(2)
                                job_cards = self.get_job_cards(current_url)
                                job_cards_objects = [self.make_hashable(card) for card in job_cards]
                    except Exception as e:
                        stop += 1

            except Exception as e:
                print(f"An error occurred: {e}")

    def get_jobs(self, use_temp_profile=False, need_login=True, apply=True):
        if need_login:
            self.login_to_linkedin(use_temp_profile)
        for url_ in self.urls:
            self.driver.get(url_)
            logging.info("Navigated to LinkedIn jobs page")
            if url_ == 'https://www.linkedin.com/jobs/':
                self.scroll_page()
                # TODO: DEBUG AND FIX THIS METHOD
                # self.process_jobs_in_page(self.driver.current_url)
                valid_urls = self.filter_urls()
                print(f'valid_urls = {valid_urls}')
                for url in valid_urls:
                    try:
                        self.process_url(url, apply=apply)
                    except:
                        continue
            else:
                self.process_url(url_, apply=apply)

        logging.info("Scraping process complete")

    @staticmethod
    def get_source(job):
        try:
            a_element = job.find_element(By.XPATH, ".//a[contains(@class, 'job-card-list__title')]")
            source = a_element.get_attribute("href")
            return source
        except Exception as e:
            print(f"Exception occur: {e}")
            return None

    def login_to_linkedin(self, use_temp_profile):
        try:
            username, password = self.get_user_details(use_temp_profile)

            self.driver.get('https://www.linkedin.com/login')
            logging.info("Navigated to LinkedIn login page")
            try:
                logging.info("Attempting to log in")
                self.driver.find_element(By.ID, 'username').send_keys(username)
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

    def filter_urls(self):
        filtered_elements = []
        while len(filtered_elements) <= 1:
            a_elements = self.get_a_elements()
            if a_elements:
                for a_element in a_elements:
                    try:
                        aria_label = a_element.get_attribute("aria-label")
                        href = a_element.get_attribute("href")
                        if aria_label and href and "Show all" in aria_label and "linkedin.com/jobs/" in href:
                            filtered_elements.append(href)
                    except Exception as e:
                        print(f"Error accessing an element: {e}")
                return filtered_elements

    def get_scrollable_div(self):
        if self.first_call_to_scrollable_div:
            self.first_call_to_scrollable_div = False
            self.scrollable_div_classname = input("What is the scrollable div classname?")
        try:
            # Primary selector: Using parent container and searching inside it
            container = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "main"))
            )
            # TODO: CHANGE THE CLASSNAME EVERY DAY, LINKEDIN CHANGE IT DYNAMICALLY !!
            scrollable_div = container.find_element(By.XPATH,
                                                    f".//div[contains(@class, '{self.scrollable_div_classname}')]")
            return scrollable_div
        except Exception as e:
            print(f"Primary selector failed: {e}. Attempting fallback selector.")

        try:
            # Fallback selector: More general pattern
            scrollable_div = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@id='main']//div[contains(@class, 'jobs-search-results-list')]")
                )
            )
            return scrollable_div
        except Exception as e:
            print(f"Both primary and fallback selectors failed: {e}. Attempting exact XPath.")

        try:
            scrollable_div = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "/html/body/div[6]/div[3]/div[4]/div/div/main/div/div[2]/div[1]/div")
                )
            )
            return scrollable_div
        except Exception as e:
            print(f"Exact XPath selector failed: {e}. No element found.")
            return None

    def get_a_elements(self):
        """
        Find and return all the <a> elements that share a common class name, and contains
        the URL for the job pages on LinkedIn.

        :return: a_elements (list)
        """
        stop = 0
        while stop <= 5:
            try:
                time.sleep(2)
                a_elements = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, '[aria-label^="Show all"]'))
                )

                return a_elements
            except Exception as e:
                stop += 1
                continue
        return None

    def scroll_page(self, DOWN=True, FIND_SECTION=False):
        if FIND_SECTION:
            section_xpath = "//section[contains(@class, 'artdeco-card') and contains(@class, 'discovery-templates-vertical-list')]"
            section_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, section_xpath))
            )
            self.driver.execute_script("arguments[0].scrollIntoView();", section_element)
        if DOWN:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        else:
            self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        return

    def process_job_card(self, job_card):
        source = self.get_source(job_card)
        if not source:
            return None

        response = llm_with_tools.get_llm_response(
            PROMPTS.CREATE_JOB_PROMPT.format(source=source, job_desc=job_card.text))
        job_obj = llm_with_tools.execute_function_from_response(response)
        return job_obj

    def apply_for_job(self, job_card):
        # Step 1: scroll to the specific job card
        self.driver.execute_script("arguments[0].scrollIntoView();", job_card)
        time.sleep(2)
        # Step 2: click on it to open the job popup
        job_card.click()
        time.sleep(2)
        # Step 3: look for the easy apply button
        if self.get_and_press_easy_apply_btn():
            while True:
                time.sleep(2)
                job_popup = self.get_apply_popup()
                if job_popup:
                    # Step 4: process the popup and extract all fields
                    select_fields = self.get_fields(type_='select', popup=job_popup)
                    input_fields = self.get_fields(type_='input', popup=job_popup)
                    checkbox_fields = self.get_fields(type_='checkbox', popup=job_popup)
                    radio_fields = self.get_fields(type_='radio', popup=job_popup)

                    # Step 5: check if we need to fill any field, or they already filled
                    if checkbox_fields:
                        self.check_for_fill_fields(type_='checkbox', fields=checkbox_fields)
                    if select_fields:
                        self.check_for_fill_fields(type_='select', fields=select_fields)
                    if input_fields:
                        self.check_for_fill_fields(type_='input', fields=input_fields)
                    if radio_fields:
                        self.check_for_fill_fields(type_='radio', fields=radio_fields)
                    # Step 6: scroll down the popup, and get the submit button
                    self.driver.execute_script("arguments[0].scrollIntoView();", job_popup)
                    button, button_type = self.get_button_type()
                    self.driver.execute_script("arguments[0].click();", button)
                    if button_type == 'submit':
                        return True
                    elif button_type == 'review':
                        return self.handle_review()

    def get_and_press_easy_apply_btn(self):
        stop = 0

        while stop <= 5:
            try:
                wait = WebDriverWait(self.driver, 10)
                button = wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//button[contains(@aria-label, 'Easy Apply') and contains(@class, 'jobs-apply-button')]")
                    )
                )
                button.click()
                print("Clicked on the 'Easy Apply' button.")
                return True
            except Exception as e:
                print(f"Error: {e}")
                stop += 1

        return False

    def get_apply_popup(self):
        stop = 0
        while stop <= 5:
            try:
                wait = WebDriverWait(self.driver, 10)
                popup = wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH,
                         "//div[contains(@class, 'artdeco-modal__content') and contains(@class, 'jobs-easy-apply-modal__content')]")
                    )
                )
                print("Popup located successfully!")
                return popup
            except Exception as e:
                print(f"Error from process_apply_popup(): {e}")
                stop += 1
        return None

    def get_fields(self, popup, type_):
        stop = 0
        while stop <= 5:
            try:
                if type_.lower() == 'select':
                    select_elements = popup.find_elements(By.XPATH, ".//select")
                    return select_elements if len(select_elements) > 0 else None
                elif type_.lower() == 'input':
                    input_elements = popup.find_elements(By.XPATH, ".//input")
                    return input_elements if len(input_elements) > 0 else None
                elif type_.lower() == 'checkbox':
                    checkbox_elements = popup.find_elements(By.XPATH, ".//input[@type='checkbox']")
                    return checkbox_elements if len(checkbox_elements) > 0 else None
                elif type_.lower() == 'radio':
                    radio_elements = popup.find_elements(By.XPATH, ".//input[@type='radio']")
                    radio_elements_with_details = self.get_details_from_radio(radio_elements, popup)
                    return radio_elements_with_details if len(radio_elements_with_details) > 0 else None
            except Exception as e:
                print(f"Error from get_fields(): {e}")
                stop += 1
        return None

    def check_for_fill_fields(self, type_, fields):
        """
        Process a list of fields to find their parent div, extract instructions,
        and determine if they need to be filled.

        Args:
            type_ (str): The type of fields ("select" or "input").
            fields (list): A list of WebElement fields to process.

        Returns:
            list: Fields that need to be filled, along with their instructions.
        """
        choices = []
        stop = 0
        while stop <= 5:
            for field in fields:
                try:
                    # self.driver.find_elements(By.XPATH, "//div[contains(@class, 'fb-dash-form-element')]")
                    parent_div = field.find_element(By.XPATH,
                                                    "./ancestor::div[contains(@class, 'fb-dash-form-element')]")
                    instruction_text = None
                    try:
                        instruction_text = parent_div.find_element(By.XPATH, ".//label").text.strip()
                    except:
                        instruction_text = parent_div.text

                    is_filled = False
                    if type_ == "select":
                        selected_value = field.get_attribute("value")
                        if selected_value and selected_value != "Select an option":
                            is_filled = True
                    elif type_ == "input":
                        field_value = field.get_attribute("value")
                        if field_value and field_value.strip():
                            is_filled = True
                    elif type_ == "checkbox":
                        is_checked = field.get_attribute("checked")
                        if "I Agree Terms & Conditions" in instruction_text:
                            if not is_checked:
                                field.click()
                                is_filled = True
                        else:
                            if is_checked:
                                is_filled = True
                            else:
                                choices = self.get_choices(parent_div, field, instruction_text)

                    elif type_ == "radio":
                        radio_field = field['radio']
                        if radio_field.is_selected():
                            is_filled = True
                        choices = field['label']
                    if not is_filled:
                        to_fill = {"field": field, "instruction": instruction_text}
                        press_enter = True if type_ in ['checkbox', 'radio'] else False
                        response, is_city = self.get_answer_for_field(type_, instruction_text, choices)

                        # Scroll to the field (if needed)
                        self.driver.execute_script("arguments[0].scrollIntoView();", field)
                        # Send keys to the field (if needed)
                        field.send_keys(response)
                        if press_enter or is_city:
                            field.send_keys(Keys.RETURN)
                except Exception as e:
                    print(f"Error processing field: {e}")
                    stop += 1
            return True
        if stop == 5:
            return False
        return True

    def get_answer_for_field(self, type_, instruction_text, choices=None):
        """
        Generate a concise and pure response from the LLM for a given field.

        Args:
            type_ (str): The type of the field.
            instruction_text (str): Instructions on what the response should include.

        Returns:
            str: The pure response from the LLM without intro/outro content.
            :param type_:
            :param instruction_text:
            :param choices:
        """
        try:
            # Remove leading/trailing whitespace and both types of quotes
            def clean_response(response):
                response = response.strip().strip('"').strip("'")
                match = re.search(r'\d+', response)
                if match:
                    return int(match.group(0))
                return response

            if 'website' in instruction_text.lower():
                return "https://github.com/an1604", False
            elif "LinkedIn Profile" in instruction_text:
                return "https://www.linkedin.com/in/aviv-nataf-757aa1247/"
            elif "How did you hear about this job" in instruction_text:
                return "LinkedIn", False
            elif instruction_text.lower() in ["city", 'location (city)']:
                return "Rishon LeZion, Center District, Israel", True
            elif "salary expectations" in instruction_text.lower() or "compensation expectations" in instruction_text.lower():
                return "10000", False
            elif "work experience" in instruction_text:
                try:
                    domain = instruction_text.split("How many years of work experience do you have with")[-1].strip()
                    prompt = PROMPTS.get_work_experience_prompt(domain)
                    chain = prompt | self.llm
                    inpt = {"domain": domain}
                    response = self.get_response(chain, inpt, True)
                    return clean_response(response), False
                except Exception as e:
                    print(f"Error: {e}")
                    return "1", False
            else:
                while True:
                    choices = "\n".join(choices) if len(choices) > 0 else "No options provided."
                    prompt = PROMPTS.get_fill_field_prompt(type_=type_, instruction_text=instruction_text,
                                                           choices=choices)
                    if prompt:
                        chain = prompt | self.llm
                        inpt = {"type_": type_, "instruction_text": instruction_text}
                        response = self.get_response(chain, inpt)
                        return clean_response(response), False
        except ValueError as e:
            print(f"Error from get_answer_for_field(): {e}")

    def get_button_type(self):
        """
        Attempts to locate either the 'Submit application' or 'Continue to next step' button in the job popup.
        Returns:
            tuple: A WebElement and a string indicating the type of button located,
                   or None if no button is found within the retries.
        """
        stop = 0
        job_popup = self.get_apply_popup()
        while stop <= 5:
            try:
                submit_button = WebDriverWait(job_popup, 10).until(
                    EC.presence_of_element_located((By.XPATH,
                                                    "//button[contains(@aria-label, 'Submit application') and contains(@class, 'artdeco-button')]"))
                )
                return submit_button, 'submit'
            except Exception as e:
                print(f"Attempt {stop + 1}: 'Submit application' button not found. Trying 'Continue to next step'...")

            try:
                review_button = WebDriverWait(job_popup, 10).until(
                    EC.presence_of_element_located((By.XPATH,
                                                    "//button[contains(@aria-label, 'Review') and contains(@class, 'artdeco-button')]"))
                )
                return review_button, 'review'
            except Exception:
                print(f"Attempt {stop + 1}: 'Review' button not found. Retrying...")

            try:
                next_button = WebDriverWait(job_popup, 10).until(
                    EC.presence_of_element_located((By.XPATH,
                                                    "//button[contains(@aria-label, 'Continue to next step') or contains(@aria-label, 'Next') and contains(@class, 'artdeco-button')]"))
                )
                return next_button, 'continue'
            except Exception as e:
                print(f"Attempt {stop + 1}: 'Continue to next step' button not found. Retrying...")

            stop += 1
        print("Failed to locate either button after 5 retries.")
        return None, 'None'

    def handle_review(self):
        # Step 1: Scroll to the bottom of the job_popup
        job_popup = self.get_apply_popup()
        self.driver.execute_script("arguments[0].scrollIntoView();", job_popup)
        stop = 0
        while stop <= 5:
            try:
                button, button_type = self.get_button_type()
                if button_type == 'submit':
                    self.driver.execute_script("arguments[0].click();", button)
                    return True
            except Exception as e:
                print(f"Error from handle_review(): {e}")
                stop += 1
        return False

    def get_job_cards(self, current_url):
        if self.driver.current_url != current_url:
            self.driver.get(current_url)

        stop = 0
        while stop <= 5:
            try:
                wait = WebDriverWait(self.driver, 10)
                job_list_container = wait.until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'job-card-container')]"))
                )
                job_cards = job_list_container.find_elements(By.XPATH, "//div[contains(@data-job-id, 'search')]")
                return job_cards
            except Exception as e:
                print(f"Error from get_job_cards(): {e}")
                stop += 1
        return set()

    def handle_done_popup(self):
        import linkedin.linkedinFunctions as lf
        stop = 0
        while stop <= 5:
            try:
                popup = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//div[contains(@class, 'artdeco-modal') and contains(@role, 'dialog')]"))
                )
                print("Popup located.")

                done_button = WebDriverWait(popup, 10).until(
                    EC.element_to_be_clickable((By.XPATH,
                                                "//button[contains(@class, 'artdeco-button') and contains(@class, 'artdeco-button--primary') and contains(., 'Done')]"))
                )
                done_button.click()
                return True
            except Exception as e:
                lf.findButtonFromType(self.driver, btn_type="Done")
                lf.findButtonFromType(self.driver, btn_type="Not now")
                print(f"An error occurred while handling the popup: {e}")
                stop += 1
        return False

    def apply_and_save_job(self, job_card, job_obj):
        current_url = self.driver.current_url
        easy_apply = False
        if "easy apply" in job_card.text.lower():
            easy_apply = True
            if self.apply_for_job(job_card) and job_obj:
                self.handle_done_popup()
                self.save_job_to_pending_jobs_collection(job_obj)
                self.driver.get(current_url)
                time.sleep(2)
        elif job_obj:
            print("Job created")
            job_obj.set_job_element(job_card)
            Job.write_job_to_file(job_obj.to_dict(), self.jobs_filepath)
        return current_url, easy_apply

    @staticmethod
    def save_job_to_pending_jobs_collection(job_obj):
        from agents.Server.db import add_job_to_pending_jobs

        add_job_to_pending_jobs(job_obj)
        print(f"Job {job_obj.job_title} added to pending jobs!")

    @staticmethod
    def get_response(chain, inpt, need_int=False):
        while True:
            response = chain.invoke(input=inpt)
            response = response.strip()

            if need_int:
                try:
                    response = int(response)
                    return response
                except ValueError:
                    continue
            if not any(phrase in response.lower() for phrase in
                       ["here's", "here is", "hope this helps", "thank you", "best regards"]):
                return response

    @staticmethod
    def get_choices(parent_div, field, instruction_text):
        try:
            labels = parent_div.find_elements(By.XPATH,
                                              f"//label[@for='{field.get_attribute('id')}']").text.strip()
            choices = [label if label else instruction_text for label in labels]
            return choices
        except Exception as e:
            try:
                labels = parent_div.find_elements(By.XPATH,
                                                  f"//label[@for='{field.get_attribute('class')}']").text.strip()
                choices = [label if label else instruction_text for label in labels]
                return choices
            except Exception as e:
                return []

    @staticmethod
    def make_hashable(job_card):
        try:
            title_element = job_card.find_element(By.XPATH, ".//a[contains(@class, 'job-card-container__link')]")
            job_title = title_element.text.strip()
            company_element = job_card.find_element(By.XPATH,
                                                    ".//div[contains(@class, 'artdeco-entity-lockup__subtitle')]")
            company_name = company_element.text.strip()
            return (job_title, company_name)
        except Exception as e:
            print(f"Error making job card hashable: {e}")
            return None

    @staticmethod
    def get_details_from_radio(radio_elements, popup):
        if len(radio_elements) > 0:
            radio_details = []
            for radio in radio_elements:
                try:
                    label_xpath = f".//label[@for='{radio.get_attribute('class')}']"
                    label_element = popup.find_element(By.XPATH, label_xpath)
                    radio_details.append({
                        "radio": radio,
                        "label": label_element.text.strip() if label_element else None
                    })
                except Exception as e:
                    print(f"Error from get_details_from_radio(): {e}")
                    continue
            return radio_details
        return []

    @staticmethod
    def get_user_details(use_temp_profile):
        if use_temp_profile:
            username = LINKEDIN_TEMP_USERNAME
            password = LINKEDIN_TEMP_PASSWORD
        else:
            username = LINKEDIN_USERNAME
            password = LINKEDIN_PASSWORD
        return username, password

    def scrape_specific_job(self, use_temp_profile, apply, job_title="Junior software developer"):
        from linkedin_scraper import JobSearch, actions

        username, password = self.get_user_details(use_temp_profile)
        actions.login(self.driver, username, password)
        try:
            job_search = JobSearch(driver=self.driver, close_on_complete=False, scrape=False)
            job_listings = job_search.search(
                job_title)  # returns the list of `Job` from the first page
        except:
            pass
        url = self.driver.current_url
        self.process_url(url, get_url=False, apply=apply,
                         pagination_xpath="//ul[contains(@class, 'jobs-search-pagination__pages')]")
        print("Done")

    @staticmethod
    def get_rand_job(jobs, jobs_set):
        job_choice = random.choice(jobs)
        while job_choice in jobs_set:
            job_choice = random.choice(jobs)
        jobs_set.add(job_choice)
        return job_choice

    def stop(self):
        self.driver.quit()
        self.driver = None


if __name__ == '__main__':
    agent = Linkedin_agent()
    try:
        # agent.process_url(
        #     "https://www.linkedin.com/jobs/search/?currentJobId=4082471200&geoId=101620260&keywords=Easy%20Apply%20jobs&origin=JOB_COLLECTION_PAGE_SEARCH_BUTTON&refresh=true",
        #     init_driver=True)
        agent.scrape_specific_job(use_temp_profile=False, apply=True,
                                  job_title='Junior software developer')
    except:
        pass

    agent.get_jobs(need_login=True, use_temp_profile=False, apply=True)
    # agent.get_external_jobs_and_auto_apply()
