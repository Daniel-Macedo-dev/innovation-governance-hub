FROM python:3.12-slim
WORKDIR /app
RUN useradd --create-home appuser
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY . .
RUN mkdir -p data/uploads templates && chown -R appuser:appuser /app
USER appuser
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]

