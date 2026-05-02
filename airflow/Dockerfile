FROM apache/airflow:2.9

USER root
COPY feanor/ /opt/feanor-src/
RUN pip install --no-cache-dir /opt/feanor-src

USER airflow
