# Job Form Agent

An AI agent that fills job and placement application forms (Google Forms) from your resume and profile, while keeping you in control of every answer.

It reads the form, finds answers from your profile and resume, searches for missing information on its own, asks you only for what it can't find, fills the form in your browser, and lets you review everything. **It never clicks Next or Submit — you do.**

## Features

- **Resume reading** — extracts your details from `resume.pdf` and fills gaps in your profile. Values you typed yourself always take priority.
- **Self-search for missing answers** — before asking you, the agent checks your earlier answers, the full resume text, and safe derivations (e.g. first name from full name). It never guesses or converts grades.
- **Asks only what's left** — required fields first, with numbered options and input validation.
- **Written answers need your approval** — for questions like *"Why do you want to join?"*, you choose: AI draft (accept / rewrite with feedback / replace), type it yourself, or skip.
- **Answer memory** — optionally remembers what you typed, so the next form is filled automatically.
- **Multi-page forms** — after you click *Next* in the browser, the agent fills the new page automatically. Going *Back* never overwrites your answers.
- **Review before moving on** — every answer is shown with its source (profile, resume, earlier answer, AI draft, typed by you) and can be edited by number.
- **Works with sign-in-required forms** — connects to a normal Chrome window where you signed in yourself.
- **Free LLM options** — any OpenAI-compatible API: Groq (cloud, free tier), Gemini, or Ollama (runs fully on your laptop). Automatic retries and fallback to a backup model.

## Security design

This project treats form pages and resumes as **untrusted input**:

- **Prompt-injection resistance** — form questions and resume text are marked untrusted in every prompt, and instructions hidden inside them are ignored.
- **Output validation** — every LLM answer is checked before use: options must match exactly, dates must be valid, placeholders are rejected.
- **Sensitive fields are never automated** — Aadhaar, PAN, passport, bank/UPI details, passwords and OTPs are never auto-filled, never sent to the LLM, never saved to memory, and hidden in logs.
- **Human in the loop** — the agent never submits; AI-written text is used only after you approve it.
- **No secrets in code** — API keys live in `.env`; personal data, login cookies and memory files are excluded by `.gitignore`.
- **Privacy option** — use Ollama to keep all personal data on your own machine.

## How it works

```
resume.pdf + profile.json
          │
          ▼
  ┌───────────────┐   ┌──────────────┐   ┌─────────────┐   ┌──────────┐   ┌─────────┐
  │ Read the page │ → │ Pass 1:      │ → │ Pass 2:     │ → │ Ask user │ → │ Fill +  │
  │ (Playwright)  │   │ match profile│   │ self-search │   │ for rest │   │ review  │
  └───────────────┘   └──────────────┘   └─────────────┘   └──────────┘   └─────────┘
          ▲                                                                     │
          └──────────── user clicks Next → agent fills the next page ───────────┘
```

## Setup

Requires Python 3.10+ and Google Chrome.

```bash
git clone https://github.com/Laxitasojitra/job-form-agent.git
cd job-form-agent
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python -m playwright install chromium
```

1. Copy `.env.example` to `.env` and add an LLM API key (e.g. a free key from https://console.groq.com/keys).
2. Copy `profile.example.json` to `profile.json` and fill in your details (anything left as `FILL_ME` is looked up in your resume or asked).
3. Put your resume in the project folder as `resume.pdf`.

Check the setup:

```bash
python list_models.py       # confirms the API key works and shows available models
python resume_reader.py     # shows what the agent learned from your resume
```

## Usage

```bash
start_chrome.bat            # Windows: opens a separate Chrome window - sign in to Google there once
python agent.py             # paste the form link when asked
```

For forms that don't need sign-in, you can skip `start_chrome.bat`.

To create a test form with every question type (including prompt-injection and sensitive-field traps), paste `createTestForm.gs` into https://script.google.com and run it.

## Project structure

| File | Purpose |
|---|---|
| `agent.py` | Main loop: page by page — read, find answers, ask, fill, review |
| `form_reader.py` | Extracts questions, types and options from a Google Form |
| `resume_reader.py` | Reads the resume PDF and fills gaps in the profile (cached) |
| `llm_mapper.py` | Two-pass answer finding and validation |
| `writer.py` | Written answers: AI draft with your approval, or your own text |
| `ask_user.py` | Terminal questions for missing fields |
| `answer_memory.py` | Remembers your answers; sensitive-field detection |
| `llm_client.py` | LLM calls with retries, backup model and JSON clean-up |
| `browser.py` | Connects to your Chrome, or opens its own browser |
| `list_models.py` | Lists models available to your API key |

## Current limitations

- Supports Google Forms only (other portals like Workday are planned).
- Time, linear scale, grid and file-upload questions are not filled yet — fill them in the browser.
- `start_chrome.bat` is for Windows.

## Disclaimer

Built for learning and personal use. Always review answers before submitting — you are responsible for what you submit. Respect each website's terms of service.
