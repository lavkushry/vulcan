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

# Inject public SSH key for passwordless Ansible execution
RUN mkdir -p /home/vulcan/.ssh && chmod 700 /home/vulcan/.ssh
COPY keys/id_ed25519.pub /home/vulcan/.ssh/authorized_keys
RUN chmod 600 /home/vulcan/.ssh/authorized_keys && \
    chown -R vulcan:vulcan /home/vulcan/.ssh

# Configure OpenSSH daemon
RUN sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    echo "ClientAliveInterval 30" >> /etc/ssh/sshd_config && \
    echo "ClientAliveCountMax 5" >> /etc/ssh/sshd_config

EXPOSE 22

CMD ["/usr/sbin/sshd", "-D"]
