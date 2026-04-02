FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# C/C++ — LLVM/Clang
# Python — already on Ubuntu
# Java — OpenJDK
# Rust — rustup
# Go — golang
RUN apt-get update && apt-get install -y \
    clang llvm \
    python3 python3-pip \
    openjdk-17-jdk \
    golang-go \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Python Azure SDK
RUN pip3 install azure-storage-blob azure-data-tables

WORKDIR /app
COPY compile_server.py .

EXPOSE 8080
CMD ["python3", "compile_server.py"]
