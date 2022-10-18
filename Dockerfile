ARG SOURCE_CONTAINER_TAG
FROM python:${SOURCE_CONTAINER_TAG}
WORKDIR /usr/local/src
COPY src/ pyproject.toml ./
ARG PROJECT_NAME LISTEN_IP LISTEN_PORT
ENV PROJECT_NAME=${PROJECT_NAME} LISTEN_IP=${LISTEN_IP} LISTEN_PORT=${LISTEN_PORT}
WORKDIR /usr/local/src/${PROJECT_NAME}
RUN python -m pip install --upgrade pip && pip install poetry
RUN useradd -m ${PROJECT_NAME}
RUN poetry export -o /tmp/logparser-requirements.txt
RUN apt update && apt -y install strace
USER ${PROJECT_NAME}
ENV PATH="${PATH}:${HOME}/.local/bin"
RUN pip install -r /tmp/logparser-requirements.txt
ARG TARGET MONITOR_PERIOD POLLING_FREQUENCY REQUEST_TIMEOUT TARGET
WORKDIR /home/${PROJECT_NAME}
COPY templates/ ./templates
CMD /usr/local/src/${PROJECT_NAME}/poller.py --listen-ip ${LISTEN_IP} --listen-port ${LISTEN_PORT} --monitor-period ${MONITOR_PERIOD} --polling-frequency ${POLLING_FREQUENCY} --request-timeout ${REQUEST_TIMEOUT} --target ${TARGET}
EXPOSE ${LISTEN_PORT}/tcp
