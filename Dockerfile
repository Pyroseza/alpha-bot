FROM python:3.10
COPY requirements.txt /app/
RUN pip install --no-cache-dir -U pip
RUN pip install --no-cache-dir -U -r /app/requirements.txt

