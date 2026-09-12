# ==============================================================
# Jenkins controller with a Docker client.
#
# The pipeline builds images, so Jenkins needs the docker CLI and
# the compose plugin. It does NOT run its own daemon -- it talks to
# the host's daemon through the mounted socket (see compose file).
# ==============================================================

FROM jenkins/jenkins:lts-jdk21

USER root

# docker CLI + compose plugin from Docker's own apt repo, plus the
# tools the pipeline shells out to.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg openssh-client rsync \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
        -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Pre-install the plugins the Jenkinsfile depends on, so a fresh
# controller can run the pipeline without manual plugin hunting.
COPY plugins.txt /usr/share/jenkins/ref/plugins.txt

RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

USER jenkins
