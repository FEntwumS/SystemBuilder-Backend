FROM ubuntu:22.04
# Set non-interactive mode for apt
# This prevents some packages from prompting for user input during installation
# install riscv gcc toolchain here instead of in litex_setup to avoid user input during installation
RUN apt-get update && apt-get install -y \
    wget \
    git \
    build-essential \
    verilator \
    python3.10 \ 
    python3-pip \
    python3-venv \
    gcc-riscv64-unknown-elf 
RUN apt-get clean
WORKDIR /litex

RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install setuptools wheel
RUN python3 -m venv /litex/venv

RUN wget https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py
RUN chmod +x litex_setup.py
RUN . /litex/venv/bin/activate && ./litex_setup.py --init --install --config=full

RUN . /litex/venv/bin/activate && pip3 install meson ninja
# RUN . /litex/venv/bin/activate && ./litex_setup.py --gcc=riscv
RUN apt install libevent-dev libjson-c-dev -y
COPY ./litex_generator.py .
COPY ./generator_aux_CRG.py .
COPY ./generator_aux_CSR.py .