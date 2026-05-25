FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

<<<<<<< HEAD
=======
# Create data directory for SQLite and reports
RUN mkdir -p data/reports

>>>>>>> 7721fb9 (Add full project: database, models, llm, search, prompts, utils, frontend, requirements, Dockerfile)
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]