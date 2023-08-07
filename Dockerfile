FROM python:3.9
RUN apt-get update -y
RUN apt-get install wget build-essential python3-dev libagg-dev libpotrace-dev pkg-config libgl1 -y

WORKDIR /
COPY requirements.txt /
RUN pip install -r requirements.txt
COPY . /
ENV PORT=5000
CMD gunicorn -w 4 'vectorizing:create_app()' --timeout 0 -b 0.0.0.0:$PORT