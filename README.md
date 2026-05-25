# AI Compliance Consultant

A SaaS MVP that automatically checks whether an AI product or service complies with the EU AI Act, providing instant analysis and recommendations.

## Features

- Simple web form to submit company/product details.
- Background web search to gather public information about the company.
- AI-powered analysis using a local LLM (Ollama `deepseek-v4-flash`) against the EU AI Act.
- Instant markdown report with:
  - Risk category classification
  - Applicable requirements
  - Identified gaps
  - Concrete recommendations
- Downloadable report (Markdown) on the same page.

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLite (SQLAlchemy)
- **Frontend**: Static HTML + Vanilla JS
- **LLM**: Ollama API with model `deepseek-v4-flash`
- **Web Search**: DuckDuckGo Instant Answer API
- **Deployable**: Docker

## Getting Started

### Prerequisites

- [Python 3.12+](https://www.python.org/downloads/)
- [Ollama](https://ollama.com/) installed and running with model `deepseek-v4-flash`:
  ```bash
  ollama run deepseek-v4-flash
  ```
- (Optional) [Docker](https://www.docker.com/products/docker-desktop) for containerized deployment.

### Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/<your-username>/ai-compliance-consultant.git
   cd ai-compliance-consultant
   ```

2. Create a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate   # on Windows: venv\\Scripts\\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Make sure Ollama is running with the required model:
   ```bash
   ollama run deepseek-v4-flash
   ```
   Keep this running in a separate terminal.

5. Start the FastAPI server:
   ```bash
   python -m app.main
   ```
   The server will be available at <http://127.0.0.1:8000>.

6. Open your browser, fill out the form, and receive your compliance report.

### Docker Deployment

1. Build the Docker image:
   ```bash
   docker build -t ai-compliance-consultant .
   ```

2. Run the container:
   ```bash
   docker run -p 8000:8000 ai-compliance-consultant
   ```
   Ensure that Ollama is accessible from within the container (if Ollama runs on the host, you may need to adjust network settings or run Ollama inside the container as well).

## Project Structure

```
ai-compliance-saas/
├─ app/
│   ├─ __init__.py
│   ├─ main.py          # FastAPI entrypoint
│   ├─ database.py      # SQLAlchemy setup
│   ├─ models.py        # DB models
│   ├─ llm.py           # Ollama wrapper
│   ├─ search.py        # Web search helper
│   ├─ prompts.py       # Prompt templates
│   ├─ utils.py         # Report generation
│   └─ templates/
│       └─ report_template.md
├─ static/
│   └─ index.html       # Frontend form
├─ data/                # SQLite DB file
├─ reports/             # Generated markdown reports
├─ requirements.txt
├─ Dockerfile
└─ README.md
```

## How It Works

1. User submits the form (`/submit` endpoint).
2. A `Submission` record is created in the SQLite database with status `pending`.
3. A background task processes the submission:
   - Performs up to three web searches (DuckDuckGo) for the company.
   - Builds a prompt combining the system prompt (EU AI Act expertise) and user data.
   - Calls the local Ollama model (`deepseek-v4-flash`) to generate analysis.
   - Generates a markdown report using a Jinja2 template.
   - Updates the submission status to `done` and stores the report path.
4. User can poll `/report/{id}` to check when the report is ready and download it.

## Future Improvements

- User authentication and history of reports.
- PDF report generation.
- Email delivery of reports.
- More sophisticated web search (SerpAPI, Google Programmable Search).
- UI improvements (progress indicator, better styling).
- Multi-language support (German, French, etc.).
- Deployment to cloud platforms (Render, Railway, Fly.io).

## License

MIT

# ai-compliance-consultantRedeploy trigger: 2026-05-25T18:26:28Z
