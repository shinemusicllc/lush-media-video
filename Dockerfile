FROM python:3.12-slim

WORKDIR /app

ARG APP_COMMIT=unknown
ENV APP_COMMIT=${APP_COMMIT}

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create runtime directories. Persistent VPS data is bind-mounted at /data.
RUN mkdir -p uploads

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
