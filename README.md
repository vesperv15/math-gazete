# arXiv Daily Math & AI Research Dispatcher

An event-driven, serverless automated data ingestion and LLM summarization pipeline. It fetches the latest research papers from the arXiv API daily, synthesizes structured paper digests using Google's Gemini API, and dispatches dynamic HTML research briefings via email.

![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Cron%20Automation-blue?logo=githubactions)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Gemini API](https://img.shields.io/badge/Google%20Gemini-LLM%20Summarization-8E75B2?logo=googlegemini)
![License](https://img.shields.io/badge/License-MIT-green)

Ingestion Layer: Queries arXiv API for target mathematical and computational categories (math.PR, math.OC, cs.AI, etc.).
LLM Synthesis Layer: Processes raw metadata through tailored contextual prompts via Google Gemini API to produce structured, concise technical summaries.
Delivery Layer: Formats paper digests into responsive HTML email templates and dispatches them automatically.
Orchestration: Fully automated serverless execution triggered daily via GitHub Actions Cron workflows.

## Tech Stack & Tools
Core Runtime: Python 3.11+
LLM Engine: Google Gemini API (google-generativeai)
Data Fetching: feedparser / arXiv REST API
Automation & CI/CD: GitHub Actions Workflow
Templating: Jinja2 / HTML Email Components

---

## Pipeline Architecture

```text
[ arXiv API ] ──> ( Data Fetcher ) ──> [ Raw Abstracts ]
                                              │
                                              ▼
[ Email Subscribers ] <── ( SMTP Engine ) <── ( Gemini API LLM Engine )
