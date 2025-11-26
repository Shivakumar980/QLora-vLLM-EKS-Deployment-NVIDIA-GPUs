FROM nvidia/cuda:12.1.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --upgrade pip

RUN pip3 install --no-cache-dir \
    "numpy<2" \
    torch==2.1.0 \
    transformers==4.36.0

RUN pip3 install --no-cache-dir \
    vllm==0.2.7

RUN pip3 install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    pydantic==2.5.0 \
    boto3==1.34.0 \
    prometheus-client==0.19.0

WORKDIR /app

COPY app.py /app/
COPY download_model.py /app/

EXPOSE 8000

CMD ["python3", "app.py"]