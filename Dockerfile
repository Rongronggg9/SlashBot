FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt /app

RUN pip install --no-cache-dir --trusted-host pypi.python.org -r /app/requirements.txt

COPY . /app

CMD ["python", "-u", "SlashBot.py"]