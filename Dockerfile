FROM python:3.10
RUN apt-get -y update
RUN apt-get -y install build-essential python-dev libagg-dev libpotrace-dev pkg-config libgl1
WORKDIR /app
COPY requirements.txt /app/
RUN pip install -r requirements.txt
COPY * /app/
CMD python /app/app.py