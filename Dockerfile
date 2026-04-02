FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install C/C++ (LLVM/Clang), Python, Java, Go
RUN apt-get update && apt-get install -y \
    clang llvm \
    python3 python3-pip \
    default-jdk \
    golang \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (rustup)
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain stable
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Python Azure SDK for blob upload from container
RUN pip3 install azure-storage-blob azure-data-tables

WORKDIR /app
COPY compile_server.py .

EXPOSE 8080
CMD ["python3", "compile_server.py"]
