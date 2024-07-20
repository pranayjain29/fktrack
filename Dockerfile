FROM python:3.12-slim

WORKDIR /app

COPY . /app

RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    libnss3 \
    libgconf-2-4 \
    libxss1 \
    libappindicator3-1 \
    libgbm-dev \
    libgtk-3-0 \
    chromium \
    && pip install --no-cache-dir -r requirements.txt

ENV PATH="/app/.wdm/drivers/chromedriver/linux64/126.0.6478.182:{PATH}"

CMD ["python", "app.py"]
