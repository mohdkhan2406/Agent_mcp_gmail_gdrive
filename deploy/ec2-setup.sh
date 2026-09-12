#!/usr/bin/env bash
#
# One-time EC2 setup: Python, Java, Jenkins, Docker.
#
# Run once on a fresh Ubuntu instance:
#
#   scp -i agentic_gmail_gdrive.pem deploy/ec2-setup.sh ubuntu@<EC2_IP>:~
#   ssh -i agentic_gmail_gdrive.pem ubuntu@<EC2_IP>
#   chmod +x ec2-setup.sh && ./ec2-setup.sh
#
# Jenkins is installed natively via apt (not in a container), so it
# can drive the host's Docker directly.

set -euo pipefail

echo "=============================================="
echo " 0/6  Preflight"
echo "=============================================="

# A full root volume surfaces as confusing build failures rather
# than a clear "disk full", so check before installing anything.
ROOT_GB=$(df -BG / | tail -1 | awk '{print $2}' | tr -dc '0-9')

# /proc/meminfo rather than free(1): always present on Linux, and
# one less package assumption on a bare AMI.
RAM_MB=$(awk '/^MemTotal:/ {print int($2/1024)}' /proc/meminfo)

: "${ROOT_GB:?could not determine root volume size}"
: "${RAM_MB:?could not determine RAM size}"

echo "Root volume: ${ROOT_GB} GB"
echo "RAM:         ${RAM_MB} MB"

if [ "${ROOT_GB}" -lt 18 ]; then
    echo
    echo "ERROR: root volume is ${ROOT_GB} GB; at least 20 GB is needed."
    echo "Jenkins, Java, Docker, both images and the build cache will"
    echo "not fit. Relaunch with 20 GiB, or grow the EBS volume and run:"
    echo "    sudo growpart /dev/nvme0n1 1 && sudo resize2fs /dev/nvme0n1p1"
    exit 1
fi

if [ "${RAM_MB}" -lt 1800 ]; then
    echo
    echo "ERROR: ${RAM_MB} MB RAM. The frontend Vite build will be"
    echo "OOM-killed below ~2 GB. Use t3.small or larger."
    exit 1
fi

echo "Preflight OK."
echo

echo "=============================================="
echo " 1/6  System packages"
echo "=============================================="

sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg wget git fontconfig

echo "=============================================="
echo " 2/6  Python"
echo "=============================================="

sudo apt-get install -y python3 python3-pip python3-venv
python3 --version

echo "=============================================="
echo " 3/6  Java 21 (required by Jenkins)"
echo "=============================================="

sudo apt-get install -y openjdk-21-jre
java -version

echo "=============================================="
echo " 4/6  Jenkins"
echo "=============================================="

sudo install -m 0755 -d /etc/apt/keyrings

sudo wget -q -O /etc/apt/keyrings/jenkins-keyring.asc \
    https://pkg.jenkins.io/debian-stable/jenkins.io-2023.key

echo "deb [signed-by=/etc/apt/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian-stable binary/" \
    | sudo tee /etc/apt/sources.list.d/jenkins.list > /dev/null

sudo apt-get update
sudo apt-get install -y jenkins

echo "=============================================="
echo " 5/6  Docker + compose plugin"
echo "=============================================="

# Docker's own repo rather than the distro's docker.io package: the
# pipeline uses `docker compose` (v2, a CLI plugin), which docker.io
# does not ship. Installing docker.io alone gives "docker: 'compose'
# is not a docker command".

sudo install -m 0755 -d /etc/apt/keyrings

sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y \
    docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin

docker --version
docker compose version

echo "=============================================="
echo " 6/6  Permissions"
echo "=============================================="

# Jenkins builds images, so its service user needs the docker socket.
sudo usermod -aG docker jenkins
sudo usermod -aG docker ubuntu
sudo usermod -aG jenkins ubuntu

# The deploy stage writes to /opt/agent-gmail-gdrive and chowns the
# mounted secrets to the container user, which needs root. Grant just
# those two commands rather than blanket sudo.
sudo tee /etc/sudoers.d/jenkins-deploy > /dev/null <<'SUDOERS'
jenkins ALL=(ALL) NOPASSWD: /bin/chown, /usr/bin/chown, /bin/mkdir, /usr/bin/mkdir
SUDOERS
sudo chmod 0440 /etc/sudoers.d/jenkins-deploy
sudo visudo -c -f /etc/sudoers.d/jenkins-deploy

sudo mkdir -p /opt/agent-gmail-gdrive/secrets
sudo chown -R jenkins:jenkins /opt/agent-gmail-gdrive

sudo systemctl enable jenkins docker
sudo systemctl restart docker
sudo systemctl restart jenkins

sleep 10

echo
echo "=============================================="
echo " Done"
echo "=============================================="
echo
systemctl is-active jenkins docker || true
echo
echo "Jenkins URL:  http://$(curl -s -m 5 ifconfig.me || echo '<EC2_PUBLIC_IP>'):8080"
echo "Username:     admin"
echo -n "Password:     "
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
echo
echo "Security group must allow inbound:"
echo "  22   SSH   -- your IP only"
echo "  8080 Jenkins -- your IP only (an open Jenkins is a remote shell)"
echo "  80   App"
echo
