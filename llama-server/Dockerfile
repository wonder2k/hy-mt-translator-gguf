FROM ubuntu:24.04

RUN apt-get update && apt-get install -y \
    git build-essential cmake curl ca-certificates libcurl4-openssl-dev libssl-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone https://github.com/ggml-org/llama.cpp.git

WORKDIR /opt/llama.cpp

RUN cmake -B build \
    -DLLAMA_BUILD_SERVER=ON \
    -DLLAMA_CURL=ON \
    -DLLAMA_OPENSSL=ON \
 && cmake --build build --config Release --target llama-server -j"$(nproc)"

ENV LLAMA_HF_REPO=sj5430/HY-MT1.5-1.8B-Q4_K_M-GGUF
ENV LLAMA_HF_FILE=hy-mt1.5-1.8b-q4_k_m.gguf
ENV LLAMA_CTX_SIZE=1024
ENV LLAMA_THREADS=8
ENV LLAMA_PORT=8080
ENV LD_LIBRARY_PATH=/opt/llama.cpp/build/src:/opt/llama.cpp/build/ggml/src

EXPOSE 8080

CMD ["/opt/llama.cpp/build/bin/llama-server", \
  "--hf-repo", "sj5430/HY-MT1.5-1.8B-Q4_K_M-GGUF", \
  "--hf-file", "hy-mt1.5-1.8b-q4_k_m.gguf", \
  "-c", "1024", \
  "-t", "8", \
  "--host", "0.0.0.0", \
  "--port", "8080"]
