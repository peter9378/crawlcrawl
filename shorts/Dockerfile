FROM python:3.8-slim

COPY . .

WORKDIR /app

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]
