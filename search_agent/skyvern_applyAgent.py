import requests


class skyvern_applyAgent:
    def __init__(self):
        pass

    @staticmethod
    def apply_to_external_website(job_url):
        url = "http://localhost:8000/api/v1/tasks"
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
                "current_gpa": "81",
                "school_option": "Other",
                "school_name": "The college of management",
                "expected_graduation_date": "March 2025",
                "are_you_a_student": "yes",
                "salary_expectations": "10000"
            },
            "url": job_url,
            "proxy_location": "RESIDENTIAL",
            "totp_identifier": None,
            "totp_verification_url": None,
            "webhook_callback_url": None,
        }
        headers = {
            "Content-Type": "application/json"
        }
        response = requests.post(url, json=payload, headers=headers)
        print("Status Code:", response.status_code)
        print("Response Body:", response.text)
