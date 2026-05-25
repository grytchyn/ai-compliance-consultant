<<<<<<< HEAD
from . import memory  # we will use memory tool? Actually memory is a Hermes tool, we cannot import it. Instead we will hardcode the system prompt from memory.
# In this environment we cannot call memory tool from within the code (the code runs outside Hermes). 
# So we will embed the system prompt directly, pulled from the known memory fact.
# For simplicity, we define the system prompt as a constant.
SYSTEM_PROMPT = """Ты – эксперт по EU AI Act. Высокорисковые ИИ‑системы: биометрия, критичная инфраструктура, найм, кредит‑scoring, образование. Основные требования: риск‑менеджмент, управление данными, прозрачность, человеческий надзор, ведение журнала событий, оценка соответствия.
Отвечай строго по пунктам, используй только факты из предоставленного контекста."""

def get_system_prompt() -> str:
    return SYSTEM_PROMPT

def build_user_prompt(company: str, url: str, description: str, search_results: list) -> str:
    # Format search results
    search_text = ""
    for idx, r in enumerate(search_results, start=1):
        title = r.get('title', 'No title')
        link = r.get('url', '')
        snippet = r.get('snippet', '')
        search_text += f"{idx}. {title}\n   URL: {link}\n   Сниппет: {snippet}\n\n"
    if not search_text:
        search_text = "Данные из открытых источников не найдены."
    prompt = f"""Проанализируй следующую компанию и её продукт с точки зрения EU AI Act.
Компания: {company}
Сайт: {url}
Описание продукта: {description}
Сведения из открытых источников:
{search_text}
На основании этого определи:
1) Попадает ли продукт под высокорисковую категорию (Да/Нет/Недостаточно данных).
2) Какие требования AI Act вероятно применимы (список).
3) Выявленные gaps (чего не хватает для соблюдения).
4) Конкретные рекомендации (документы, процессы, контрольные точки).
Ответ оформи в markdown с заголовками: **Вывод**, **Категория риска**, **Применимые требования**, **Gaps**, **Рекомендации**, **Источники**.
Если данных недостаточно – укажи, какая информация нужна."""
    return prompt
=======
SYSTEM_PROMPT = (
    "You are an AI compliance expert specializing in the European Union AI Act (Regulation (EU) 2021/XXXX). "
    "You have deep knowledge of the AI Act's risk categories, prohibited AI systems, high‑risk requirements, "
    "transparency obligations, conformity assessment procedures, post‑market monitoring, and penalties. "
    "When given a company description and any publicly available information, you must: "
    "(1) Determine whether the company's AI‑related activities fall under the AI Act scope, "
    "(2) Classify the risk level (Unacceptable, High, Limited, Minimal) according to the Act, "
    "(3) List the specific articles and requirements that apply, "
    "(4) Identify any gaps between the described practices and the Act's obligations, "
    "(5) Provide concrete, actionable recommendations to achieve compliance, "
    "(6) Cite relevant sources (e.g., official AI Act text, EU guidelines) where possible. "
    "Answer in clear, structured Markdown with the following sections: "
    "## Output\n## Risk Category\n## Applicable Requirements\n## Identified Gaps\n## Recommendations\n## Sources\n"
)

def build_user_prompt(company: str, url: str, description: str, search_results: str) -> str:
    prompt = f"""
Company: {company}
Website: {url}
Description: {description}

Publicly available information (from web search):
{search_results}

Based on the above, produce a compliance report regarding the EU AI Act.
"""
    return prompt.strip()
>>>>>>> 7721fb9 (Add full project: database, models, llm, search, prompts, utils, frontend, requirements, Dockerfile)
