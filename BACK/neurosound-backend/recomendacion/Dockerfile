FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home api
COPY shared shared
COPY config config
COPY recomendacion recomendacion
USER api
EXPOSE 8000
CMD ["uvicorn", "recomendacion.app:app", "--host", "0.0.0.0", "--port", "8000"]
