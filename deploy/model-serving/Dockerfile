ARG SGLANG_IMAGE
FROM ${SGLANG_IMAGE}

# The caller must provide a pinned image; no version or compatibility is guessed.
ARG SGLANG_IMAGE
RUN python3 -c 'import re, sys; value = sys.argv[1]; assert re.fullmatch(r"[a-z0-9][a-z0-9./:_-]*@sha256:[0-9a-f]{64}", value) and ":latest@" not in value, "SGLANG_IMAGE must use a pinned sha256 digest"' "$SGLANG_IMAGE"
ENV SANMOU_BASE_IMAGE=${SGLANG_IMAGE} \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /opt/sanmou-serving
COPY scripts/model-serving/validate_manifest.py /opt/sanmou-serving/validate_manifest.py
COPY deploy/model-serving/launch.py /opt/sanmou-serving/launch.py
EXPOSE 30000
ENTRYPOINT ["python3", "/opt/sanmou-serving/launch.py"]
CMD ["/run/sanmou/manifest.json"]
