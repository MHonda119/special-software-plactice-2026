FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Install a copy of the entrypoint into a location not overwritten by bind-mounts
# and normalize line endings inside the image to avoid CRLF shebang problems.
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/entrypoint.sh

# Also keep app-local copy executable for image-built usage
RUN if [ -f /app/entrypoint.sh ]; then sed -i 's/\r$//' /app/entrypoint.sh || true; fi

# Use explicit shell interpreter to avoid shebang/CRLF issues when mounting from Windows
ENTRYPOINT ["sh", "/usr/local/bin/entrypoint.sh"]

CMD ["gunicorn", "lecture_system.wsgi:application", "--bind", "0.0.0.0:8000"]
