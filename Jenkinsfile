// ================================================================
// Agent MCP -- Gmail + Google Drive
//
// Build -> smoke test -> push -> deploy to EC2 over SSH.
//
// Secrets are NEVER in the repo. Jenkins injects them as
// credentials and copies them to the host at deploy time:
//
//   agent-env                 Secret file  -> secrets/.env
//   google-credentials-json   Secret file  -> secrets/credentials.json
//   google-token-json         Secret file  -> secrets/token.json
//   ec2-ssh-key               SSH private key (agentic_gmail_gdrive.pem)
//   dockerhub-creds           Username/password (only if PUSH_IMAGES)
// ================================================================

pipeline {

    agent any

    parameters {
        string(
            name: 'DEPLOY_HOST',
            defaultValue: '',
            description: 'EC2 public DNS or IP. Leave empty to build and test only.'
        )
        string(
            name: 'DEPLOY_USER',
            defaultValue: 'ubuntu',
            description: 'SSH user: ubuntu for Ubuntu AMIs, ec2-user for Amazon Linux.'
        )
        string(
            name: 'REGISTRY_NAMESPACE',
            defaultValue: '',
            description: 'Docker Hub username or org. Required when PUSH_IMAGES is ticked.'
        )
        booleanParam(
            name: 'PUSH_IMAGES',
            defaultValue: false,
            description: 'Push images to a registry. If off, images are built on the deploy host.'
        )
    }

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
    }

    environment {
        BACKEND_IMAGE  = 'agent-gmail-gdrive-backend'
        FRONTEND_IMAGE = 'agent-gmail-gdrive-frontend'
        COMPOSE_PROJECT_NAME = 'agent-gmail-gdrive'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                script {
                    // Immutable tag per build, plus a moving 'latest'.
                    def sha = sh(
                        script: 'git rev-parse --short HEAD',
                        returnStdout: true
                    ).trim()
                    env.IMAGE_TAG = "${env.BUILD_NUMBER}-${sha}"
                }
                sh 'git --no-pager log -1 --oneline'
                echo "Building tag ${env.IMAGE_TAG}"
            }
        }

        stage('Guard: no secrets committed') {
            steps {
                // A committed token.json or .env is a live credential
                // leak. Fail loudly rather than build and ship it.
                sh '''
                    set -e
                    leaked=$(git ls-files | grep -E '(^|/)(\\.env|credentials\\.json|token\\.json)$' || true)
                    if [ -n "$leaked" ]; then
                        echo "SECRET COMMITTED TO GIT:"
                        echo "$leaked"
                        exit 1
                    fi
                    echo "No secrets tracked in git."
                '''
            }
        }

        stage('Build images') {
            steps {
                sh '''
                    set -e
                    docker build -t "${BACKEND_IMAGE}:${IMAGE_TAG}"  -t "${BACKEND_IMAGE}:latest"  ./backend
                    docker build -t "${FRONTEND_IMAGE}:${IMAGE_TAG}" -t "${FRONTEND_IMAGE}:latest" ./frontend
                    docker images | grep agent-gmail-gdrive
                '''
            }
        }

        stage('Smoke test') {
            steps {
                // Boot the backend with throwaway credentials and assert
                // it serves, loads its MCP tools, and routes correctly.
                // No real Google account is touched.
                sh '''
                    set -e

                    rm -rf .smoke && mkdir -p .smoke
                    echo "OPENAI_API_KEY=sk-smoke-test-not-real" > .smoke/.env

                    docker rm -f agent-smoke >/dev/null 2>&1 || true

                    docker run -d --name agent-smoke \
                        --env-file .smoke/.env \
                        -e GOOGLE_CREDENTIALS_FILE=/secrets/credentials.json \
                        -e GOOGLE_TOKEN_FILE=/secrets/token.json \
                        -p 18000:8000 \
                        "${BACKEND_IMAGE}:${IMAGE_TAG}"

                    for i in $(seq 1 30); do
                        if curl -fsS -m 3 http://127.0.0.1:18000/ >/dev/null 2>&1; then
                            echo "backend up after ${i}s"
                            break
                        fi
                        sleep 1
                    done

                    curl -fsS -m 10 http://127.0.0.1:18000/ | grep -q '"status":"online"'

                    # MCP tools must load, or every query fails at runtime.
                    docker logs agent-smoke 2>&1 | grep -q "search_gmail"
                    docker logs agent-smoke 2>&1 | grep -q "search_google_drive"

                    # Routing works with no credentials: off-topic queries
                    # are rejected before any Google call is attempted.
                    curl -fsS -m 10 -X POST http://127.0.0.1:18000/query \
                        -H 'Content-Type: application/json' \
                        -d '{"query":"what is the weather"}' | grep -q "could not tell"

                    # A Drive query must fail fast with an auth message
                    # rather than hang waiting on a browser prompt.
                    curl -fsS -m 20 -X POST http://127.0.0.1:18000/query \
                        -H 'Content-Type: application/json' \
                        -d '{"query":"search drive for resume"}' | grep -qi "authorization needed"

                    echo "SMOKE TEST PASSED"
                '''
            }
            post {
                always {
                    sh 'docker rm -f agent-smoke >/dev/null 2>&1 || true; rm -rf .smoke || true'
                }
            }
        }

        stage('Push images') {
            when {
                expression { return params.PUSH_IMAGES }
            }
            steps {
                script {
                    if (!params.REGISTRY_NAMESPACE?.trim()) {
                        error('PUSH_IMAGES is on but REGISTRY_NAMESPACE is empty.')
                    }
                }
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub-creds',
                    usernameVariable: 'REG_USER',
                    passwordVariable: 'REG_PASS'
                )]) {
                    sh '''
                        set -e
                        echo "$REG_PASS" | docker login -u "$REG_USER" --password-stdin

                        for img in "${BACKEND_IMAGE}" "${FRONTEND_IMAGE}"; do
                            docker tag "${img}:${IMAGE_TAG}" "${REGISTRY_NAMESPACE}/${img}:${IMAGE_TAG}"
                            docker tag "${img}:${IMAGE_TAG}" "${REGISTRY_NAMESPACE}/${img}:latest"
                            docker push "${REGISTRY_NAMESPACE}/${img}:${IMAGE_TAG}"
                            docker push "${REGISTRY_NAMESPACE}/${img}:latest"
                        done

                        docker logout
                    '''
                }
            }
        }

        stage('Deploy to EC2') {
            when {
                expression { return params.DEPLOY_HOST?.trim() }
            }
            steps {
                withCredentials([
                    sshUserPrivateKey(
                        credentialsId: 'ec2-ssh-key',
                        keyFileVariable: 'SSH_KEY'
                    ),
                    file(credentialsId: 'agent-env',               variable: 'ENV_FILE'),
                    file(credentialsId: 'google-credentials-json', variable: 'GCRED_FILE'),
                    file(credentialsId: 'google-token-json',       variable: 'GTOKEN_FILE')
                ]) {
                    sh '''
                        set -e

                        KNOWN_HOSTS="/tmp/known_hosts_${BUILD_NUMBER}"
                        SSH_OPTS="-i ${SSH_KEY} -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=${KNOWN_HOSTS}"
                        TARGET="${DEPLOY_USER}@${DEPLOY_HOST}"
                        APP_DIR="/opt/agent-gmail-gdrive"

                        # ---- prepare the remote directory ----
                        ssh ${SSH_OPTS} "${TARGET}" "sudo mkdir -p ${APP_DIR}/secrets && sudo chown -R \\$(id -u):\\$(id -g) ${APP_DIR}"

                        # ---- ship the build context ----
                        tar czf /tmp/app_${BUILD_NUMBER}.tgz \
                            --exclude=backend/venv \
                            --exclude=frontend/node_modules \
                            --exclude=secrets \
                            --exclude='*.pem' \
                            docker-compose.yml backend frontend

                        scp ${SSH_OPTS} /tmp/app_${BUILD_NUMBER}.tgz "${TARGET}:${APP_DIR}/app.tgz"
                        rm -f /tmp/app_${BUILD_NUMBER}.tgz

                        # ---- ship secrets (never in git, never in an image) ----
                        scp ${SSH_OPTS} "${ENV_FILE}"    "${TARGET}:${APP_DIR}/secrets/.env"
                        scp ${SSH_OPTS} "${GCRED_FILE}"  "${TARGET}:${APP_DIR}/secrets/credentials.json"
                        scp ${SSH_OPTS} "${GTOKEN_FILE}" "${TARGET}:${APP_DIR}/secrets/token.json"

                        # ---- unpack and start ----
                        # token.json is rewritten when the access token
                        # refreshes, so the container user must own it.
                        ssh ${SSH_OPTS} "${TARGET}" "
                            set -e
                            cd ${APP_DIR}
                            tar xzf app.tgz && rm -f app.tgz
                            chmod 600 secrets/.env secrets/credentials.json secrets/token.json
                            sudo chown -R 10001:10001 secrets
                            export FRONTEND_PORT=80
                            export BACKEND_PORT=8001
                            docker compose up -d --build --remove-orphans
                            docker image prune -f
                            docker compose ps
                        "

                        rm -f "${KNOWN_HOSTS}"
                    '''
                }
            }
        }

        stage('Verify deployment') {
            when {
                expression { return params.DEPLOY_HOST?.trim() }
            }
            steps {
                sh '''
                    set -e

                    for i in $(seq 1 30); do
                        if curl -fsS -m 5 "http://${DEPLOY_HOST}/" >/dev/null 2>&1; then
                            echo "frontend reachable"
                            break
                        fi
                        sleep 10
                    done

                    # The API must answer through nginx, not just the page.
                    curl -fsS -m 20 -X POST "http://${DEPLOY_HOST}/api/query" \
                        -H 'Content-Type: application/json' \
                        -d '{"query":"what is the weather"}' | grep -q "could not tell"

                    echo "DEPLOYMENT VERIFIED: http://${DEPLOY_HOST}/"
                '''
            }
        }
    }

    post {
        success {
            echo "OK  ${env.IMAGE_TAG}"
        }
        failure {
            echo "FAILED ${env.IMAGE_TAG} -- see the stage log above"
        }
        always {
            sh 'docker rm -f agent-smoke >/dev/null 2>&1 || true'
            cleanWs()
        }
    }
}
