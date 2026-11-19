FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PORT=8080
# no requirements.txt found in the repo
COPY . .
RUN useradd --create-home app && chown -R app /app
USER app
EXPOSE 8080
CMD ["python", "app.py"]
