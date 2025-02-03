import json
import os


class FileManager:
    def __init__(self, from_server=False):
        if from_server:
            self.server_dir = os.getcwd()
            self.main_dir = os.path.dirname(self.server_dir)  # Parent dir
        else:
            # get the parent of the parent
            self.main_dir = self.get_main_dirpath()
            self.server_dir = os.path.join(self.main_dir, 'Server')

        self.traffic_agent_dir = os.path.join(os.path.dirname(self.main_dir), 'traffic_agent')
        self.mail_manager_dir = os.path.join(os.path.dirname(self.main_dir), 'mail')
        self.companies_dir = os.path.join(self.main_dir, 'companies')
        self.selenuim_dir = os.path.join(self.main_dir, 'selenuim')
        self.all_agents_dir = os.path.join(self.selenuim_dir, 'agents')
        self.json_jobs_dir = os.path.join(self.selenuim_dir, 'json_jobs')
        self.resume_filepath = self.get_resume_filepath(format_='txt')
        self.resume_pdf_filepath = self.get_resume_filepath(format_='pdf')

    def get_path_from_traffic_agent(self, dirname='messages'):
        try:
            path = os.path.join(self.traffic_agent_dir, dirname)
            os.makedirs(path, exist_ok=True)
            return os.path.abspath(path)
        except:
            return None

    def get_path_from_mail_manager(self, filename):
        try:
            path = os.path.join(self.mail_manager_dir, filename)
            return os.path.abspath(path)
        except:
            return None

    @staticmethod
    def get_filename_by_company(company_name, dir_path):
        try:
            path = os.path.join(dir_path, f"{company_name}.json")
            if not os.path.exists(path):
                os.makedirs(dir_path, exist_ok=True)
            return path
        except Exception as e:
            return None

    def get_prompt_filepath(self, filename):
        try:
            msgs_dir = self.get_path_from_traffic_agent()
            if msgs_dir:
                path = os.path.join(self.traffic_agent_dir, msgs_dir, filename)
                if os.path.exists(path):
                    return path
            return None
        except Exception as e:
            return None

    def get_jobs_filepath(self, agent_name):
        try:
            path = os.path.join(self.json_jobs_dir, agent_name + '.json')
            if not os.path.exists(path):
                os.makedirs(self.json_jobs_dir, exist_ok=True)
                with open(path, 'w') as file:
                    json.dump([], file)
            return path
        except Exception as e:
            print(f"Exception occurred in get_jobs_filepath: {e}")
            return None

    def get_path_from_companies(self, file_name):
        try:
            path = os.path.join(self.companies_dir, file_name)
            if os.path.exists(path):
                return path
            return None
        except Exception as e:
            print(f"Exception occur from get_path_from_companies: {e}")
            return None

    @staticmethod
    def get_main_dirpath():
        try:
            path = os.getcwd()
            parts = path.split(os.sep)  # Split the path into parts based on the separator
            first_agents_index = parts.index('agents')  # Find the first occurrence of 'agents'
            first_agents_path = os.sep.join(parts[:first_agents_index + 1])  # Join up to the first 'agents'
            return first_agents_path
        except Exception as e:
            parent_dir = os.path.dirname(os.getcwd())
            agents_path = os.path.join(parent_dir, "agents")
            print(f"Error: {e}. Defaulting to {agents_path}")
            return agents_path

    def get_resume_filepath(self, format_):
        if format_ == 'txt':
            path = os.path.join(self.main_dir, 'resume.txt')
        else:
            path = os.path.join(self.main_dir, 'aviv_nataf_resume.pdf')
        if os.path.exists(path):
            return path
        return None


file_manager = FileManager()
