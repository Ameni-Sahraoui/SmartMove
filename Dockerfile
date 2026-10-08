FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m smartmove && chown -R smartmove:smartmove /app
USER smartmove
EXPOSE 8501
CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8501"]
