FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

RUN cd backend && DJANGO_SECRET_KEY=build-placeholder POSTGRES_DB=x POSTGRES_USER=x POSTGRES_PASSWORD=x python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["bash", "-c", "cd backend && daphne -b 0.0.0.0 -p 8000 config.asgi:application"]
