<<<<<<< HEAD
import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from . import models

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR = Path("app/templates")
env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

def generate_report_md(submission: models.Submission, llm_answer: str, search_results: list) -> str:
    template = env.get_template("report_template.md")
    from datetime import datetime
    rendered = template.render(
        company=submission.company,
        url=submission.url,
        description=submission.description,
        llm_answer=llm_answer,
        search_results=search_results,
        now=datetime.now()
    )
    return rendered

def save_report(submission_id: int, md_content: str) -> str:
    report_path = REPORTS_DIR / f"{submission_id}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    return str(report_path)
=======
from jinja2 import Environment, FileSystemLoader
import os
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

def render_report(report_md: str) -> str:
    # In this simple version, we just return the markdown as is.
    # Could be extended to render HTML via markdown library.
    return report_md

def save_report(report_md: str, sub_id: str) -> str:
    report_dir = Path(__file__).parent.parent / "data" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    file_path = report_dir / f"report_{sub_id}.md"
    file_path.write_text(report_md, encoding="utf-8")
    return str(file_path)
>>>>>>> 7721fb9 (Add full project: database, models, llm, search, prompts, utils, frontend, requirements, Dockerfile)
