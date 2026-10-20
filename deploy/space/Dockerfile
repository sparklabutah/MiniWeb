# The MiniWeb public demo as a Hugging Face Docker Space (MINIWEB_DEMO=1: src/miniweb/app/demo.py).
# scripts/push_space.py uploads the repository with this file as the Space's Dockerfile. To build it yourself, from the
# repository root:
#     docker build -f deploy/space/Dockerfile -t miniweb-demo .
#     docker run -p 7860:7860 miniweb-demo          # then http://localhost:7860
# The image holds the code and the translation model; deploy/space/start.sh downloads the data on every start.

# --- the translation site's NLLB model, converted to CTranslate2 int8 (torch is needed for this step only) ---
FROM python:3.11-slim AS nllb
RUN pip install --no-cache-dir torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir transformers==4.57.6 ctranslate2==4.8.1 sentencepiece==0.2.2 protobuf==6.33.6 \
        huggingface_hub==0.36.2
WORKDIR /build
COPY src/miniweb/scripts/fetch_translation_model.py src/miniweb/scripts/
RUN python src/miniweb/scripts/fetch_translation_model.py

# --- the app ---
FROM python:3.11-slim
# Spaces run the container as user 1000
RUN useradd -m -u 1000 user
WORKDIR /home/user/app
COPY deploy/space/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY --chown=user --from=nllb /build/models models
COPY --chown=user . .
USER user
ENV HOME=/home/user PYTHONUNBUFFERED=1 MINIWEB_DEMO=1 PORT=7860
EXPOSE 7860
CMD ["sh", "deploy/space/start.sh"]
