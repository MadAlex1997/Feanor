FROM apache/airflow:3.2.1-python3.11

USER root
COPY feanor/ /opt/feanor-src/
RUN pip install --no-cache-dir /opt/feanor-src

USER airflow
RUN pip install --no-cache-dir apache-airflow-providers-fab
