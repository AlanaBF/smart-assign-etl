FROM python:3.11-slim

WORKDIR /app

COPY flowcase_etl/requirements.txt .
RUN pip install --no-cache-dir --only-binary :all: -r requirements.txt

COPY . .
RUN pip install --no-cache-dir -e .

RUN useradd --create-home appuser
USER appuser

CMD ["python", "-m", "flowcase_etl_pipeline.cli", "--generate-fake"]
