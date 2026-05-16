FROM apache/airflow:3.2.1-python3.11
USER airflow
COPY airflow/wheels /tmp/feanor-wheels
RUN pip install --no-cache-dir --find-links /tmp/feanor-wheels feanor && \
    pip install --no-cache-dir apache-airflow-providers-fab
