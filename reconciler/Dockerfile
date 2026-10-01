FROM python:3.11-slim

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && useradd --create-home --uid 1000 reconciler

# Numeric so Kubernetes can enforce runAsNonRoot
USER 1000
ENV PIPELINE_CATALOGUE_URL=https://github.com/Australian-Imaging-Service/pipelines/releases/latest/download/pipeline-release.json
ENTRYPOINT ["pydra2app", "ext", "xnat", "deploy-pipelines"]
