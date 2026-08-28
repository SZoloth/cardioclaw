FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY cardioclaw ./cardioclaw
COPY cardio_claw.py serve.py cover.png ./

RUN python -m pip install --upgrade pip \
    && python -m pip install .

RUN useradd --create-home --uid 10001 cardioclaw \
    && mkdir -p /data \
    && chown -R cardioclaw:cardioclaw /app /data

USER cardioclaw

EXPOSE 5000

CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "--access-logfile", "/dev/null", "serve:app"]
