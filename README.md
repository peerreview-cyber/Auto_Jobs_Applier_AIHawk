
<div align="center">


# AIHawk: The first Jobs Applier AI Web Agent

> ℹ️ **Note:** This is an enhanced fork of the original [AIHawk by feder-cr](https://github.com/feder-cr/Jobs_Applier_AI_Agent_AIHawk). 
> We have added anti-bot evasion, Gemini support, and stability patches to keep it working in 2026.

AIHawk's core architecture remains **open source**, allowing developers to inspect and extend the codebase. However, due to copyright considerations, we have removed all third‑party provider plugins from this repository.

### 🚀 Advanced Automation Features (January 2026)

We have significantly upgraded the core engine to handle modern web architectures and provide staff-level reliability:

-   **Shadow DOM & iFrame Mastery:** AIHawk now natively traverses nested Shadow DOMs and iframes using recursive JavaScript logic. It can "see" and interact with complex web components that standard Selenium scripts miss.
-   **Ghost Watchdog (60s Timeout):** Prevent loops and wasted time. If a form is too complex, the bot logs a timeout, **leaves the Chrome tab open for your manual review**, and opens a fresh tab to continue the rest of your applications.
-   **Per-Job Audit Logging:** Every application is documented in its own log file in `data_folder/output/job_logs/`. This includes the exact resume path used and every AI-generated answer for complete transparency.
-   **Always-Tailored Resumes:** The bot ignores generic site-saved resumes and generates a unique, job-specific PDF for **every single application** using Gemini, ensuring maximum ATS compatibility.
-   **Privacy & Agreement Automation:** AIHawk automatically detects and answers "Privacy Policy" and "Accuracy of Information" dropdowns (Yes/No) that often block basic automation.
-   **Unblockable Interaction:** Uses a JavaScript-first clicking engine to bypass invisible overlays and "element click intercepted" errors.
-   **Fully Autonomous Mode:** Set `auto_skip_waiting: true` in your config to allow the bot to run for hours without needing human intervention in the terminal.

---

### 🛠️ Quick Start

1.  **Clone & Install:**
    ```bash
    git clone https://github.com/peerreview-cyber/Auto_Jobs_Applier_AIHawk.git
    cd Auto_Jobs_Applier_AIHawk
    pip install -r requirements.txt
    ```

2.  **Initialize Data Folder:**
    ```bash
    cp -r data_folder_example data_folder
    ```

3.  **Configure Credentials:**
    - Get a free API Key from [Google AI Studio](https://aistudio.google.com/).
    - Open `data_folder/secrets.yaml` and set your key:
      ```yaml
      llm_api_key: "YOUR_GEMINI_API_KEY"
      ```

4.  **Set AI Model & Preferences:**
    - Open `data_folder/config.yaml`.
    - Set the model to Gemini:
      ```yaml
      llm_model_type: "gemini"
      llm_model: "gemini-2.0-flash"
      ```
    - Update your job search criteria (locations, positions, etc.) in the same file.
    - Fill in your professional details in `data_folder/plain_text_resume.yaml`.

5.  **Run:**
    ```bash
    python3 main.py
    ```

---

AIHawk has been featured by major media outlets:

[**Business Insider**](https://www.businessinsider.com/aihawk-applies-jobs-for-you-linkedin-risks-inaccuracies-mistakes-2024-11)
[**TechCrunch**](https://techcrunch.com/2024/10/10/a-reporter-used-ai-to-apply-to-2843-jobs/)
[**Semafor**](https://www.semafor.com/article/09/12/2024/linkedins-have-nots-and-have-bots)
[**Dev.by**](https://devby.io/news/ya-razoslal-rezume-na-2843-vakansii-po-17-v-chas-kak-ii-boty-vytesnyaut-ludei-iz-protsessa-naima.amp)
[**Wired**](https://www.wired.it/article/aihawk-come-automatizzare-ricerca-lavoro/)
[**The Verge**](https://www.theverge.com/2024/10/10/24266898/ai-is-enabling-job-seekers-to-think-like-spammers)
[**Vanity Fair**](https://www.vanityfair.it/article/intelligenza-artificiale-candidature-di-lavoro)
[**404 Media**](https://www.404media.co/i-applied-to-2-843-roles-the-rise-of-ai-powered-job-application-bots/)

