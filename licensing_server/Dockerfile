FROM python:3.14-slim
WORKDIR /srv
COPY licensing_server/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home stc && mkdir /data && chown stc:stc /data
COPY licensing_server /srv/licensing_server
USER stc
EXPOSE 8765
CMD ["python", "-m", "licensing_server.server", "--data", "/data", "--host", "0.0.0.0", "--trusted-proxy", "172.29.60.2/32"]
