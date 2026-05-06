FROM ubuntu:24.04 AS builder

RUN apt-get update && apt-get install -y \
    git build-essential cmake curl ca-certificates libcurl4-openssl-dev libssl-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone https://github.com/ggml-org/llama.cpp.git

WORKDIR /opt/llama.cpp

# 显式开启 OpenSSL 和 CURL，避免 HTTPS 下载 Hugging Face 模型时报错
RUN cmake -B build \
    -DLLAMA_BUILD_SERVER=ON \
    -DLLAMA_CURL=ON \
    -DLLAMA_OPENSSL=ON \
 && cmake --build build --config Release --target llama-server -j"$(nproc)"

FROM ubuntu:24.04

RUN apt-get update && apt-get install -y \
    ca-certificates libgomp1 libssl3 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /opt/llama.cpp/build/bin/llama-server /usr/local/bin/llama-server

ENV LLAMA_HF_REPO=sj5430/HY-MT1.5-1.8B-Q4_K_M-GGUF
ENV LLAMA_HF_FILE=hy-mt1.5-1.8b-q4_k_m.gguf
ENV LLAMA_CTX_SIZE=1024
ENV LLAMA_THREADS=8
ENV LLAMA_PORT=8080

EXPOSE 8080

CMD ["/usr/local/bin/llama-server", \
  "--hf-repo", "${LLAMA_HF_REPO}", \
  "--hf-file", "${LLAMA_HF_FILE}", \
  "-c", "${LLAMA_CTX_SIZE}", \
  "-t", "${LLAMA_THREADS}", \
  "--host", "0.0.0.0", \
  "--port", "${LLAMA_PORT}"]
