# AIHawk Project Architecture

This document provides a high-level overview of the AIHawk project architecture.

## 1. Overview

AIHawk is a Python-based application designed to automate the process of applying for jobs on AIHawk. It uses Selenium for web browser automation and a language model (LLM) to answer questions during the application process.

The application can be run in two modes:

*   **Apply Mode:** Searches for jobs based on specified criteria and automatically applies for them.
*   **Collect Mode:** Collects job data without applying.

## 2. Main Components

The project is structured into several key components, each responsible for a specific part of the application's functionality.

### 2.1. Entry Point (`main.py`)

The `main.py` file is the entry point of the application. It is responsible for:

*   **Command-Line Interface:** Uses the `click` library to provide a command-line interface for running the bot.
*   **Configuration Loading:** Reads and validates the configuration from `config.yaml` and `secrets.yaml` using the `ConfigValidator` class.
*   **Component Initialization:** Initializes the main components of the application, such as the `AIHawkBotFacade`, `AIHawkAuthenticator`, `AIHawkJobManager`, and `GPTAnswerer`.
*   **Bot Execution:** Starts the bot by calling the appropriate methods on the `AIHawkBotFacade`.

### 2.2. Configuration (`config.py` and `app_config.py`)

The application's behavior is configured through two main files:

*   **`config.py`:** Contains general application settings, such as logging levels, job search parameters (positions, locations, blacklists), and the language model to be used.
*   **`app_config.py`:** Contains application-specific configurations, such as the minimum log level and minimum wait time.

### 2.3. AIHawk Bot Facade (`src/aihawk_bot_facade.py`)

The `AIHawkBotFacade` class acts as a facade, providing a simplified interface to the bot's core functionality. It is responsible for:

*   **Coordinating Components:** Orchestrates the interaction between the `AIHawkAuthenticator`, `AIHawkJobManager`, and `GPTAnswerer`.
*   **State Management:** Manages the state of the bot using the `AIHawkBotState` class, ensuring that operations are performed in the correct order.

### 2.4. AIHawk Authenticator (`src/aihawk_authenticator.py`)

The `AIHawkAuthenticator` class is responsible for handling the login process to AIHawk. It:

*   **Navigates to the login page.**
*   **Waits for the user to manually enter their credentials.**
*   **Handles security checks.**
*   **Verifies if the user is already logged in.**

### 2.5. AIHawk Job Manager (`src/aihawk_job_manager.py`)

The `AIHawkJobManager` is the core component of the application, responsible for the entire job application process. Its key responsibilities include:

*   **Job Search:** Constructs search URLs based on the configured parameters and navigates to the job search pages on AIHawk.
*   **Job Scraping:** Scrapes job listings from the search results pages.
*   **Job Filtering:** Filters out jobs that are on the blacklist or have already been applied to.
*   **Job Application:** Uses the `AIHawkEasyApplier` component to handle "Easy Apply" applications.
*   **Logging and Reporting:** Logs the application status to JSON files.

### 2.6. AIHawk Easy Applier (`src/aihawk_easy_applier.py`)

The `AIHawkEasyApplier` is a helper component that handles the "Easy Apply" functionality on AIHawk. It is responsible for filling out the application form and submitting it.

### 2.7. LLM Integration (`src/llm/llm_manager.py`)

The `llm_manager.py` file contains the logic for interacting with different language models (OpenAI, Claude, Ollama, Gemini). The `GPTAnswerer` class uses these models to answer questions that may appear during the job application process.

The `llm_manager.py` in `src/libs` is the one that is actively being used, as it is more feature-rich than the one in `src/llm`.

### 2.8. Data Models (`src/job.py`, `src/job_application_profile.py`)

The project uses several data classes to represent its core entities:

*   **`Job`:** Represents a job listing, containing information such as the job title, company, location, and apply method.
*   **`JobApplicationProfile`:** Represents the user's job application profile, containing information from their resume.

### 2.9. Resume Builder (`lib_resume_builder_AIHawk`)

This is an external library that is used to build a resume from a plain text file.

## 3. Workflow

The application follows this general workflow:

1.  The user runs the application from the command line, providing optional arguments.
2.  The `main` function in `main.py` is executed.
3.  The configuration is loaded and validated.
4.  The `AIHawkBotFacade` is initialized with the core components.
5.  The `AIHawkAuthenticator` handles the login process.
6.  The `AIHawkJobManager` starts the job search and application process.
7.  For each job, the bot scrapes the job details, filters it, and then applies for it using the `AIHawkEasyApplier`.
8.  If any questions are encountered during the application process, the `GPTAnswerer` is used to provide an answer.
9.  The application status is logged to JSON files.

## 4. Directory Structure

```
/
├── .github/
├── assets/
├── chrome_profile/
├── data_folder/
│   ├── output/
│   ├── config.yaml
│   ├── plain_text_resume.yaml
│   └── secrets.yaml
├── log/
├── src/
│   ├── libs/
│   │   ├── resume_and_cover_builder/
│   │   └── llm_manager.py
│   ├── llm/
│   │   └── llm_manager.py
│   ├── resume_schemas/
│   ├── __init__.py
│   ├── aihawk_authenticator.py
│   ├── aihawk_bot_facade.py
│   ├── aihawk_easy_applier.py
│   ├── aihawk_job_manager.py
│   ├── job_application_profile.py
│   ├── job_application_saver.py
│   ├── job.py
│   ├── jobContext.py
│   ├── logging.py
│   ├── strings.py
│   └── utils.py
├── venv/
├── .gitignore
├── app_config.py
├── config.py
├── CONTRIBUTING.md
├── LICENSE
├── main.py
├── README.md
├── requirements.txt
├── test_gemini_embeddings.py
└── test_gemini.py
```
