import json
import logging

from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from langchain_core.prompts import PromptTemplate

from langchain_ollama import ChatOllama

from agents.file_manager import file_manager

from agents.job import Job
from config import config


# Tool calling to create job object in runtime
class LLM(object):
    def __init__(self, model_name=config.LLM_TOOL_CALL_MODEL_NAME, bind_create_job_element=True):
        try:
            logging.info(f"Initializing LLM with tools: {model_name}")
            self.llm_with_tools = ChatOllama(model=model_name, temperature=0, format="json").bind_tools(
                [self.create_job_element])
            logging.info("LLM initialized and tools bound successfully.")
        except Exception as e:
            logging.error(f"Error while initializing LLM: {e}")
            raise

    def get_llm_response(self, prompt):
        try:
            response = self.llm_with_tools.invoke(prompt)
            logging.info("LLM invocation successful.")
            return response
        except Exception as e:
            logging.error(f"Unexpected error during LLM invocation: {e}", exc_info=True)
            return None

    def filter_suggestions(self, suggestions):
        """
        Classify suggestions by invoking the LLM with a prompt.
        """
        prompt = PROMPTS.FILTER_SUGGESTIONS_PROMPT.format(suggestions=suggestions)
        response = self.get_llm_response(prompt)
        logging.info(f"LLM classification response: {response}")
        classified_suggestions = response.get('classified_suggestions', [])
        return classified_suggestions

    def execute_function_from_response(self, response):
        try:
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logging.info("Processing tool calls from response.")
                for tool_call in response.tool_calls:
                    function_name = tool_call.get('name')
                    arguments = tool_call.get('args', {})

                    if function_name == 'create_job_element':
                        location = str(arguments.get('location', None))
                        experience = int(arguments.get('experience', 0))
                        title = str(arguments.get('job_title', None))
                        is_hybrid = bool(arguments.get('is_hybrid', False))

                        if (self.check_job_title(title.lower()) and experience > 2 and
                                not self.is_job_close(location) and not is_hybrid):
                            return None

                        else:
                            job = self.create_job_element(**arguments)
                            logging.info(f"Job created dynamically: {job.to_dict()}")
                            return job
            else:
                logging.info("No tool calls found in the response.")
                return self.process_response_from_content(response)
        except Exception as e:
            logging.error(f"Error in execute_function_from_response: {e}")
            raise

    @staticmethod
    def create_job_element(job_title: str, job_description: str, experience: int, location: str,
                           company_name: str, source: str, is_hybrid: bool = False):
        """
           Given details about a job, create a Job object.

           Args:
               job_title: The title of the job.
               job_description: The job description text.
               experience: Required years of experience.
               location: The location of the job.
               company_name: The name of the company offering the job.
               source: The job source or URL.
               is_hybrid: Indicates if the job is hybrid (default is False).

           Returns:
               Job: A Job object initialized with the provided details.
           """
        try:
            # Input validation
            if job_title is None or not isinstance(job_title, str):
                return None
            if job_description is None or not isinstance(job_description, str):
                return None
            if not isinstance(experience, int) or experience < 0:
                return None
            if location is None or not isinstance(location, str):
                return None
            if company_name is None or not isinstance(company_name, str):
                return None
            if source is None or not isinstance(source, str):
                return None
            logging.info("Validated inputs for job creation.")

            job = Job(
                source=source,
                job_title=job_title,
                description=job_description,
                experience=experience,
                location=location,
                company=company_name,
                is_hybrid=is_hybrid,
            )
            logging.info(f"Job object created successfully: {job.to_dict()}")
            return job
        except Exception as e:
            logging.error(f"Unexpected error while creating Job object: {e}", exc_info=True)
            return None

    @staticmethod
    def check_job_title(job_title):
        not_available_titles = ['senior', 'team leader', 'ux', 'manager']  # I am a damn Junior
        for title in not_available_titles:
            if title in job_title:
                return False
        return True

    @staticmethod
    def get_coordinates(city_name):
        """
        Get latitude and longitude of a city using geopy's Nominatim geocoder.
        """
        geolocator = Nominatim(user_agent="job-location-checker")
        location = geolocator.geocode(city_name)
        if location:
            return location.latitude, location.longitude
        else:
            raise ValueError(f"Could not find location for {city_name}")

    def is_job_close(self, job_location, city_name='Rishon Lezion', max_distance_km=60):
        """
        Check if a job is within a certain distance from a city.
        """
        try:
            city_coords = self.get_coordinates(city_name)
            job_coords = self.get_coordinates(job_location)
            distance = geodesic(city_coords, job_coords).kilometers
            return distance <= max_distance_km
        except Exception as e:
            print(f"Error occurred: {e}")
            return True  # Making sure we do not miss any opportunity

    def process_response_from_content(self, response):
        try:
            if hasattr(response, 'content') and response.content:
                logging.info("Parsing response content.")
                job_data = json.loads(response.content)

                location = str(job_data.get('location', None))
                experience = int(job_data.get('experience', 0))
                title = str(job_data.get('job_title', None))
                is_hybrid = bool(job_data.get('is_hybrid', False))

                if (self.check_job_title(title.lower()) and experience > 2 and
                        not self.is_job_close(location) and not is_hybrid):
                    logging.info("Job does not meet criteria for further processing.")
                    return None

                job = self.create_job_element(**job_data)
                logging.info(f"Job created dynamically: {job.to_dict()}")
                return job
            else:
                logging.info("No content found in the response.")
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON content: {e}")
            raise
        except Exception as e:
            logging.error(f"Error in execute_function_from_response: {e}")
            raise


llm_with_tools = LLM()


def get_resume_path():
    try:
        RESUME_FILE_PATH = file_manager.resume_filepath
        with open(RESUME_FILE_PATH, 'r', encoding='utf-8') as file:
            RESUME_TEXT = file.read()
            return RESUME_TEXT
    except Exception as e:
        print(f"Exception from get_resume_path: {e}")
        return None


class PROMPTS:
    REFINE_USER_DESCRIPTION = """
        Given the content below, summarize the user's description into 2-3 concise sentences:

        User: {user_name}
        Description: {desc}

        Guidelines:
        - Provide a precise summary based solely on the given description.
        - Avoid adding any extraneous text, explanations, or commentary beyond the requested summary.
    """

    SUMMARIZE_POSTS_TEMPLATE = """
        Summarize the given LinkedIn posts into the following format:

        <Name> is <VERY short summary of content>.
        The mail: <email>
        The link: <link>

        Posts:
        {posts}

        Ensure:
        - The summary is in plain text, following the specified format.
        - Include the "name", "content", "email", and "link" fields explicitly.
        - Do not add any additional text, explanation, or commentary.
        """

    RESUME_TEXT = get_resume_path()

    SUMMARIZE_POST_CONTENT_TEMPLATE = """
        Given the following post content, extract and summarize the relevant details with high accuracy and relevance. Specifically, extract:

        1. The email address of the post owner (likely related to a hiring post).
        2. The full name of the post owner.
        3. The company name mentioned in the post content.
        4. All links present in the post content.

        Post Content:
        {content}


        Provide the output strictly in the following JSON format:

        {{
          "email": "<email_address>",
          "name": "<post_owner_name>",
          "company": "<company_name>",
          "links": ["<link_1>", "<link_2>", ...],
          "content": "<summary_of_the_post>"
        }}

        Ensure:
        - Include all links found in the post content under the "links" key as a list. If no links are present, leave the field as an empty list ([]).
        - No additional text, explanation, or commentary outside the JSON output.
        - Leave other fields empty ("") if the information is not present in the post content.
        """

    COMPLETE_FROM_RESUME_TEMPLATE = """
        Based on the fields in the provided JSON Schema, update the `data_to_fill` field in the following JSON document using relevant information extracted from the provided resume:
        1. JSON Schema:
        {schema}
        
        2. Resume Text:
        {resume_text}

        Output the updated JSON Schema with the modified `data_to_fill` fields, ensuring relevance and accuracy. Do not include any introduction, explanation, or additional text in the response.
    """

    ANALYZE_HTML_TEMPLATE = """
                You are tasked with analyzing the following job application form:

                    1. HTML document:
                    {html}

                    2. Block-tree structure of the document:
                    {block_tree}

                    Your goal is to identify the relevant fields that need to be filled out for a job application. Based on your analysis, generate a structured JSON schema that includes the following:

                    - All required fields with their attributes (e.g., name, type, format, and any validation rules).
                    - Clear descriptions for each field.
                    - An indication of which fields are required.
                    - An additional field called `data_to_fill` for each property, which contains the suggested data to be filled based on the given `resume_text`.
                    - Locator information (`id`, `class`, or other attributes) to identify the corresponding HTML element for each field.

                    Focus on fields directly related to the job application, excluding unrelated elements like JavaScript or hidden fields unless explicitly necessary for submission.
                    Provide the JSON schema as output, without any introduction, explanation, or outro.                   
                """

    SEND_EMAIL_TEMPLATE = """
    Generate a concise and professional email for Aviv Nataf, a recent Computer Science graduate passionate about software development and cybersecurity.
    addressed to {recipient}, a hiring recruiter specializing in software development or cybersecurity roles. 
    Extract the recipient's name from the provided email address. 
    Ensure the email is precise, engaging, and directly tailored to the hiring needs. 
    Incorporate and address the following feedback: {feedback}. 

    Write ONLY the email content itself without any introduction, explanation, or outro. 
    The response must strictly consist of the email text.

    Example:
    Dear [Recruiter Name],

    I am Aviv Nataf, a recent Computer Science graduate passionate about software development and cybersecurity. 
    I am reaching out to express my interest in exploring potential opportunities where I can contribute my skills and grow as a software developer or cybersecurity engineer.

    I have attached my CV for your review. I would be thrilled to discuss how my background aligns with your hiring needs and the roles you are recruiting for.

    Looking forward to connecting with you soon!
    
    Best regards,  
    Aviv Nataf
    """

    WORK_EXPERIENCE_PROMPT = """
    Based on my Personal Information and Background, 
    determine the total number of years of experience I have in the following domain: **{domain}**.

    **Personal Information and Background:**
    {resume_in_text}

    Please return only an integer value (e.g., 2, 3, etc.) based on the details provided in my background. Do not include any additional text, explanation, or formatting. The answer must be strictly a numeric value.
    """

    FILL_FIELD_PROMPT = """
            I need you to generate a concise answer to fill a **{type_}** field for me, based on the following context:

            1. **Instruction Text:**  
               {instruction_text}

            2. **Personal Information and Background:**  
               {resume_in_text}
            
            3. If the type of the element is checkbox or radio button, choose an answer from the following options:
            {choices} 

            Make sure the answer:
            - Aligns with my skills, abilities, and professional experience.
            - Reflects the fact that I am a graduate CS student with at most **3 years of experience** in relevant fields. This is crucial for ensuring the accuracy of your response.
            - Answer precisely and accurately, and in the correct format. 
            **Do not include any introduction, explanation, or additional text—only the modified message. This requirement is critical.**
        """

    CREATE_JOB_PROMPT = """
        Use the `create_job_element` tool with the following information:
        source: {source}.
        Content: {job_desc}
    """

    FILTER_SUGGESTIONS_PROMPT = """
        Please classify each suggestion in the following list as either:
        - "company name"
        - "non-relevant search suggestion".
        Format the response as a list of objects with `suggestion` and `category`.
        Suggestions:
        {suggestions}
    """

    IS_JOB_MATCH_PROMPT = """
        According to my CV, is this job match the requirements?
        Job title: {job_title}
        Job information: {job_info}
        Job description: {job_description}
        Job requirements: {job_requirements}

        This is my CV {cv_datafile} 

        PLEASE JUST RESPOND ONLY IN TRUE/FALSE ANSWER, TO LET ME THE OPPORTUNITY TO EXECUTE INSTRUCTION IN RUNTIME ACCORDING TO YOUR ANSWER! 
    """

    @staticmethod
    def get_fill_field_prompt(type_, instruction_text, choices):
        try:
            text_formatted = PROMPTS.FILL_FIELD_PROMPT.format(
                type_=type_,
                instruction_text=instruction_text,
                resume_in_text=PROMPTS.RESUME_TEXT,
                choices=choices
            )
            print(text_formatted)
            prompt = PromptTemplate.from_template(text_formatted)
            return prompt
        except Exception as e:
            print(f"Error in get_fill_field_prompt: {e}")
            return None

    @staticmethod
    def get_work_experience_prompt(domain):
        return PromptTemplate.from_template(PROMPTS.WORK_EXPERIENCE_PROMPT.format(
            resume_in_text=PROMPTS.RESUME_TEXT,
            domain=domain
        ))

    @staticmethod
    def get_analyze_html_prompt(simplified_html, block_tree):
        prompt = PROMPTS.ANALYZE_HTML_TEMPLATE.format(
            html=simplified_html,
            block_tree=block_tree
        )
        # return PromptTemplate.from_template(prompt)
        return prompt

    @classmethod
    def get_completion_from_schema_prompt(cls, schema):
        return cls.COMPLETE_FROM_RESUME_TEMPLATE.format(schema=schema, resume_text=cls.RESUME_TEXT)
