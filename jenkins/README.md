# Jenkins setup (containerised, on the EC2 host)

> This is the **alternative** setup: Jenkins itself runs in
> Docker. For the native apt install (Jenkins installed
> directly on the instance), see [../deploy/README.md](../deploy/README.md).
> Use one or the other, not both -- they would fight over port 8080.

Jenkins runs in Docker on the EC2 box and deploys the app to that
same box. Images are built by Jenkins, pushed to Docker Hub, then
pulled back down by compose.

## 1. Prepare the instance

SSH in with the key pair:

```bash
ssh -i agentic_gmail_gdrive.pem ubuntu@<EC2_PUBLIC_DNS>
```

Install Docker if it is not already there:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
```

## 2. Start Jenkins

```bash
git clone https://github.com/mohdkhan2406/Agent_mcp_gmail_gdrive.git
cd Agent_mcp_gmail_gdrive/jenkins

DOCKER_GID=$(getent group docker | cut -d: -f3) docker compose up -d --build
```

`DOCKER_GID` matters: Jenkins builds images using the host's Docker
daemon through the mounted socket, and the `jenkins` user must be in
the host's `docker` group to open it. A wrong GID shows up as
`permission denied ... /var/run/docker.sock` in the build log.

Unlock it:

```bash
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

Then open `http://<EC2_PUBLIC_DNS>:8080`.

> **Open port 8080 is a remote shell.** Anyone who reaches this
> Jenkins can run arbitrary commands on the instance and read every
> credential stored in it. Restrict 8080 to your own IP in the
> security group, and put it behind TLS before exposing it further.

Plugins the pipeline needs are baked into the image
(see `plugins.txt`), so skip "Install suggested plugins" if you like.

## 3. Add credentials

**Manage Jenkins -> Credentials -> System -> Global**, all as
*Global* scope. The IDs must match exactly:

| ID | Kind | Content |
|---|---|---|
| `dockerhub-creds` | Username with password | Docker Hub username + an **access token**, not your password |
| `agent-env` | Secret file | Your `backend/.env` |
| `google-credentials-json` | Secret file | Your `backend/credentials.json` |
| `google-token-json` | Secret file | Your `backend/token.json` |
| `ec2-ssh-key` | SSH Username with private key | `agentic_gmail_gdrive.pem` — only needed for `ssh` deploy mode |

These files never go in git. The pipeline copies them to
`/opt/agent-gmail-gdrive/secrets/` at deploy time and `chown`s them
to uid 10001, the container user.

`token.json` must be generated first by running `auth.py` on a
machine with a browser — OAuth consent cannot run in a container.

## 4. Create the job

**New Item -> Pipeline**.

- **Pipeline script from SCM** -> Git
- Repository: `https://github.com/mohdkhan2406/Agent_mcp_gmail_gdrive.git`
- Branch: `main`
- Script Path: `Jenkinsfile`

Save, then **Build with Parameters**:

| Parameter | Value |
|---|---|
| `DEPLOY_MODE` | `local` |
| `REGISTRY_NAMESPACE` | your Docker Hub username |
| `PUSH_IMAGES` | ticked |
| `DEPLOY_HOST` | leave empty |

Run once with `DEPLOY_MODE=none` first if you want to confirm the
build and smoke test pass before anything is deployed.

## What the pipeline does

| Stage | Purpose |
|---|---|
| Checkout | Tags the build `<BUILD_NUMBER>-<short sha>` |
| Guard: no secrets committed | Fails if `.env`, `credentials.json`, `token.json` or a `.pem` is tracked in git |
| Validate config | Catches missing namespace/host before doing work |
| Build images | Backend and frontend |
| Smoke test | Boots the backend with fake credentials; asserts it serves, both MCP tools register, off-topic queries are rejected, and a Drive query fails fast instead of hanging |
| Push to Docker Hub | Pushes `:<tag>` and `:latest` |
| Deploy | `local` on this host, or `ssh` to a remote one |
| Verify deployment | Waits for both containers healthy, then exercises nginx -> backend through `/api/query` |

## Ports

| Port | Service |
|---|---|
| 80 | Frontend (nginx) |
| 8080 | Jenkins |
| 8001 | Backend, **loopback only** — the browser reaches it via `/api` |

## Troubleshooting

**`permission denied ... docker.sock`** — wrong `DOCKER_GID`. Recreate
with the value from `getent group docker | cut -d: -f3`.

**Smoke test fails on `search_gmail`** — the MCP server failed to
start. Check `docker logs` for the smoke container; usually a
missing dependency in `requirements.txt`.

**Deployed app says "Authorization needed"** — `token.json` is
missing, unreadable, or belongs to the wrong Google account. Verify
which account it authorizes:

```bash
docker exec agent-backend python -c "from mcp_server import get_drive_service; print(get_drive_service().about().get(fields='user(emailAddress)').execute())"
```

**Queries return nothing that should exist** — almost always the
wrong Google account rather than a code fault. Re-run `auth.py`,
pick the right account, and update the `google-token-json`
credential.
