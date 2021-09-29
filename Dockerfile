FROM python:3.9-slim

WORKDIR /app

COPY . /app

RUN pip install --trusted-host pypi.python.org -r /app/requirements.txt

CMD ["python", "-u", "SlashBot.py"]