# 🚀 joBot

An **AI-powered Agentic platform** designed to help job seekers **find job openings** and **increase visibility on
LinkedIn** by automating traffic and engagement.

## 🛠️ Technology Stack

![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)
![Python](https://img.shields.io/badge/Python-FFD43B?style=for-the-badge&logo=python&logoColor=blue)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-43B02A?style=for-the-badge&logo=selenium&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-3A3A3A?style=for-the-badge&logo=ollama&logoColor=white)
![Telethon](https://img.shields.io/badge/Telethon-0000FF?style=for-the-badge)
![Asyncio](https://img.shields.io/badge/Asyncio-0000FF?style=for-the-badge)

## How to Run joBot

To set up and run joBot, follow these steps:

### 1. Initialize Environment Variables

- Copy the `.env.example` file and fill in all the required parameters.

### 2. Create a Telegram Bot

- Create a Telegram bot and obtain the bot token.
    - **Guide**: [How to Create a Telegram Bot](https://www.youtube.com/watch?v=RIrIXLAj8bE)
- Create an app id and hash for the telegram client to get the monitoring and updates from telegram channels and groups.
    - **Guide**: [How to get app id and hash](https://www.youtube.com/watch?v=8naENmP3rg4)

### 3. Set Up Gmail API Secrets

- Create Gmail API credentials to enable Gmail integration.
    - **Guide**: [How to Set Up Gmail API](https://www.youtube.com/watch?v=I6KgYpHDIC8)

### 4. Configure File Paths

- Open `file_manager.py` and update the filenames and paths according to your needs.

### 5. Insert Your Resume

- Place your resume in the `/agents/Server/` directory.
- Update the `file_manager` object with the correct path to your resume.

### 6. Customize the Prompts

- Inside `agents/llm.py`, replace all instances of `"Aviv Nataf"` in the prompts with your own name.
- Review all prompts and modify them as necessary to suit your specific requirements.

### 7. Run Specific Tasks Independently

- Explore the `agents/selenium/` directory:
    - If you want to run individual tasks without setting up the entire server, you can execute each script
      independently. Results will be saved in the target directories.

### 8. Update Messages

- In the `traffic_agent/messages/` directory, replace all placeholder messages with your own details.

### 9. Find Companies Actively Hiring

- Run `/agents/tech_map.py` to discover a variety of companies that are actively hiring. This script scrapes a unique
  webpage that lists numerous companies.

### 10. Replace Resume Details

- Replace `agents/resume.txt` with your actual resume details.
    - **Tip**: You can ask ChatGPT to help format your resume content.

### 11. Install Required Packages

- Install all the necessary packages using the `requirements.txt` file:

```bash
  pip install -r requirements.txt
```

## 🔥 Important

Before running joBot, ensure the following dependencies are properly set up:

### ✅ Ollama Installation & Model Setup

- Ensure **Ollama** is installed and running on your PC.
- To download the **Llama 3.1** model, run:
  ```bash
  ollama pull llama3.1
  ```
    - If you prefer a different model, pull the desired model and update the code accordingly.

### ✅ MongoDB Setup

- Ensure **MongoDB** is installed and running on your PC.
- To simplify database management, install **MongoDB Compass** (a GUI tool).
    - **Guide**: [MongoDB Compass Tutorial](https://www.youtube.com/watch?v=gB6WLkSrtJk&t=552s)

### Additional Tips

Take a close look at each script and configuration to ensure everything aligns with your specific needs.
Customize any additional parameters or text within the prompts to better suit your application goals.

### What's next?

- Add more options and functionality to the UI.
- Make the UI look better (design).
- Fully Containerize JoBot.