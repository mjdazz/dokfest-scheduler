# Debian-based image — has libstdc++ at the FHS path that pip wheels expect,
# which is exactly what NixOS doesn't.
FROM python:3.13-slim

# libstdc++6 is usually present in slim, but installing explicitly makes the
# requirement obvious. libgomp1 is needed by numpy/ortools' OpenMP code paths.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libstdc++6 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scrape_screenings.py .

# stdin/stdout are how the script is meant to be used; container args are
# forwarded straight to the script (e.g. `--schedule`, `--solver cpsat`).
ENTRYPOINT ["python3", "/app/scrape_screenings.py"]
