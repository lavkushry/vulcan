FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install SSH server, Python 3, and administration tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    python3 \
    python3-apt \
    sudo \
    curl \
    ca-certificates \
    iproute2 \
    procps \
    net-tools \
    acl \
    systemd-sysv \
    tar \
    && rm -rf /var/lib/apt/lists/*

# Create SSH run directory
RUN mkdir -p /var/run/sshd

# Configure user vulcan with passwordless sudo
RUN useradd -m -s /bin/bash vulcan && \
    echo "vulcan:vulcan_sandbox_2026" | chpasswd && \
    echo "vulcan ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Configure OpenSSH daemon
RUN sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    echo "ClientAliveInterval 30" >> /etc/ssh/sshd_config && \
    echo "ClientAliveCountMax 5" >> /etc/ssh/sshd_config

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22

ENTRYPOINT ["/entrypoint.sh"]
