# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.10.12
FROM python:${PYTHON_VERSION}-slim as base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY . .

# Check if the file exists before attempting to chmod
RUN if [ -e "marks_bot_db.sqlite3" ]; then chmod a+rw marks_bot_db.sqlite3; fi

RUN python -m pip install -r requirements.txt

EXPOSE 8000

CMD ["python3", "source/main.py"]
