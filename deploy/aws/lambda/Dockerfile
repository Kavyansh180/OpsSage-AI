# ==============================================================================
# OpsSage AI - AWS Lambda Container Image
# Packages FastAPI backend with Mangum and pre-cached Sentence Transformers
# ==============================================================================

FROM public.ecr.aws/lambda/python:3.10

# Set environment variables for Lambda execution
# Crucial: HF_HOME must NOT be in /tmp because AWS Lambda mounts a fresh empty tmpfs
# on /tmp at runtime, which would mask build-time cached model weights!
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production \
    HF_HOME=${LAMBDA_TASK_ROOT}/model_cache \
    TRANSFORMERS_OFFLINE=0 \
    INITIALIZE_INDEXES_ON_STARTUP=false

# Copy requirements
COPY requirements.txt ${LAMBDA_TASK_ROOT}/

# Upgrade pip to handle modern wheel metadata normalization, install CPU-optimized PyTorch,
# and install backend dependencies (excluding frontend-only packages like streamlit and pandas)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple && \
    grep -v -E "^(streamlit|pandas)" ${LAMBDA_TASK_ROOT}/requirements.txt > /tmp/backend-requirements.txt && \
    pip install --no-cache-dir -r /tmp/backend-requirements.txt && \
    rm -f /tmp/backend-requirements.txt

# Pre-download Sentence Transformer model into container image during build
# Baked permanently into ${LAMBDA_TASK_ROOT}/model_cache
RUN mkdir -p ${LAMBDA_TASK_ROOT}/model_cache && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy application source code
ARG CACHEBUST=1
RUN echo "Building backend version: ${CACHEBUST}"
COPY backend ${LAMBDA_TASK_ROOT}/backend
COPY scripts ${LAMBDA_TASK_ROOT}/scripts

# Lambda handler entrypoint (delegates to Mangum adapter)
CMD ["backend.app.lambda_handler.lambda_handler"]
