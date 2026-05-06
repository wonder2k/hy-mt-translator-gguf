FROM ubuntu:24.04

RUN apt-get update && apt-get install -y \
    git build-essential cmake curl ca-certificates libcurl4-openssl-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt

# 拉取 llama.cpp 源码（官方仓库）
RUN git clone https://github.com/ggml-org/llama.cpp.git

WORKDIR /opt/llama.cpp

# 使用 CMake 构建，并开启 LLAMA_CURL
# 这样才能从 Hugging Face 拉取 GGUF 模型
RUN cmake -B build -DLLAMA_CURL=ON \
 && cmake --build build --config Release -j"$(nproc)"

# 运行时参数通过环境变量配置
ENV LLAMA_HF_REPO=sj5430/HY-MT1.5-1.8B-Q4_K_M-GGUF
ENV LLAMA_HF_FILE=hy-mt1.5-1.8b-q4_k_m.gguf
ENV LLAMA_CTX_SIZE=1024
ENV LLAMA_THREADS=8
ENV LLAMA_PORT=8080

EXPOSE 8080

# 使用 CMake 构建生成的 llama-server 可执行文件
CMD ./build/bin/llama-server \
  --hf-repo "${LLAMA_HF_REPO}" \
  --hf-file "${LLAMA_HF_FILE}" \
  -c "${LLAMA_CTX_SIZE}" \
  -t "${LLAMA_THREADS}" \
  --host 0.0.0.0 \
  --port "${LLAMA_PORT}"
