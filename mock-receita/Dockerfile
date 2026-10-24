FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DATA_DIR=/data
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY main.py .
RUN useradd --create-home --uid 1000 mock
USER mock
EXPOSE 8001
# os dados (estoque + situacao_cadastral.json) vêm do volume montado em /data
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
