FROM python:3.12-slim

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --create-home appuser

WORKDIR /home/appuser/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=appuser:appuser . .

# Vendor html2canvas so the screenshot feature works fully offline at runtime
# (bug_widget.py inlines this file if present, else falls back to a CDN).
ADD --chown=appuser:appuser \
    https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js \
    ./html2canvas.min.js

USER appuser
EXPOSE 8501

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').status==200 else 1)"

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
