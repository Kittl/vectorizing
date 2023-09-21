FROM python:3.11
RUN apt-get update -y
RUN apt-get install wget build-essential python3-dev libagg-dev libpotrace-dev pkg-config libgl1 -y

WORKDIR /
COPY requirements/dev.txt /
RUN pip install -r dev.txt
COPY . /
ENV PORT=5000
CMD gunicorn -w 4 'vectorizing:create_app()' --timeout 0 -b 0.0.0.0:$PORT