FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install .
# the OKF bundle is mounted at /app/okf_bundle (read-only) by docker-compose
ENV OKF_BUNDLE_DIR=/app/okf_bundle
EXPOSE 8001
CMD ["okf-chat", "serve", "--host", "0.0.0.0", "--port", "8001"]
