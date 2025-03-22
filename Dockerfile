FROM apache/airflow:2.10.5

WORKDIR /rizqi-workdir

COPY requirements.txt ./

RUN pip install --upgrade pip

USER root

RUN chmod -R g+rw /tmp/

USER airflow

RUN pip install -r requirements.txt
