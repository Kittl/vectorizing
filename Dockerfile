FROM python:3.9
RUN apt-get update -y
RUN apt-get install wget build-essential python3-dev libagg-dev libpotrace-dev pkg-config libgl1 -y

WORKDIR /app
COPY requirements.txt /app
RUN pip install -r requirements.txt
COPY . /app
