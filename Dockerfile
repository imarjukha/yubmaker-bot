FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN mkdir -p data

ENV PYTHONUNBUFFERED=1

CMD ["python", "-u", "main.py"]
