FROM python:3.11

ENV PYTHONUNBUFFERED=1     PYTHONDONTWRITEBYTECODE=1     PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends     build-essential     gcc     g++     binutils     libproj-dev     proj-bin     gdal-bin     libgdal-dev     libgeos-dev     netcat-openbsd     gettext     curl     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . .
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

CMD ["./docker-entrypoint.sh"]