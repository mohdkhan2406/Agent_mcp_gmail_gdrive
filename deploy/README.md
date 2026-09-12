# Deploy to EC2 (Jenkins installed natively)

This follows the reference walkthrough: Jenkins and Docker installed
directly on an Ubuntu EC2 instance with `apt`, Jenkins on 8080, the
app served on 80.

For the containerised-Jenkins alternative see [../jenkins/README.md](../jenkins/README.md).
Use one or the other, not both — they would fight over port 8080.

## 1. Launch the instance

| Setting | Value |
|---|---|
| AMI | Ubuntu Server 24.04 LTS |
| Instance type | **t3.small or larger** (2 GB RAM) |
| Storage | **20 GiB gp3 — change this at launch** |
| Key pair | `agentic_gmail_gdrive.pem` |

> **The storage default is 8 GiB, which is not enough.** Raise it to
> 20 GiB under *Configure storage* before launching. Jenkins, Java,
> Docker, both images and the build cache do not fit in 8 GiB, and a
> full root volume shows up as confusing build failures rather than a
> clear "disk full". Growing the volume later means resizing the EBS
> volume and the filesystem — easier to get right up front.

> **t2.micro / t3.micro will not work.** The frontend image runs a
> Vite production build, and Node runs out of memory on 1 GB. The
> reference uses t3.small (2 GB) for the same reason.

Rough disk budget for the 20 GiB:

| Item | Size |
|---|---|
| Ubuntu + Java + Jenkins + Docker | ~4 GB |
| Backend image | 511 MB |
| Frontend image | 74 MB |
| Build cache, layers, npm/pip downloads | ~5-8 GB |
| Headroom | remainder |

The pipeline runs `docker image prune -f` after each deploy, which
keeps old tagged images from accumulating.

### Security group inbound rules

| Port | Source | Why |
|---|---|---|
| 22 | **Your IP only** | SSH |
| 8080 | **Your IP only** | Jenkins |
| 80 | `0.0.0.0/0` | The app |

Do not open 8080 to the world. Anyone who reaches Jenkins can run
commands as root on the instance and read every stored credential —
including the Google token that grants access to your mail.

## 2. Run the setup script

```bash
chmod 400 agentic_gmail_gdrive.pem

scp -i agentic_gmail_gdrive.pem deploy/ec2-setup.sh ubuntu@<EC2_PUBLIC_IP>:~
ssh -i agentic_gmail_gdrive.pem ubuntu@<EC2_PUBLIC_IP>

chmod +x ec2-setup.sh
./ec2-setup.sh
```

It installs Python, Java 21, Jenkins and Docker, adds `jenkins` to
the `docker` group, grants the narrow sudo rights the deploy stage
needs, and prints the Jenkins unlock password.

Two deliberate differences from the reference walkthrough:

- **Docker comes from Docker's own apt repo, not `docker.io`.** The
  pipeline uses `docker compose` (v2, a CLI plugin) and `docker.io`
  does not ship it — you would get `docker: 'compose' is not a
  docker command`.
- **`jenkins` gets scoped sudo** for `chown`/`mkdir` only, via
  `/etc/sudoers.d/jenkins-deploy`, rather than blanket sudo. The
  deploy stage needs to hand the mounted secrets to the container
  user (uid 10001) and nothing more.

Log out and back in after the script runs, so your own shell picks
up the new `docker` group membership.

## 3. Unlock Jenkins

Open `http://<EC2_PUBLIC_IP>:8080`. The script prints the password;
to fetch it again:

```bash
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

Install suggested plugins, then add these if missing:
**Docker Pipeline**, **SSH Agent**, **Credentials Binding**,
**Pipeline: Stage View**, **Timestamper**, **Workspace Cleanup**.

## 4. Add credentials

**Manage Jenkins → Credentials → System → Global.** IDs must match
exactly:

| ID | Kind | Content |
|---|---|---|
| `dockerhub-creds` | Username with password | Docker Hub username + **access token** |
| `agent-env` | Secret file | `backend/.env` |
| `google-credentials-json` | Secret file | `backend/credentials.json` |
| `google-token-json` | Secret file | `backend/token.json` |
| `ec2-ssh-key` | SSH private key | `agentic_gmail_gdrive.pem` (only for `ssh` deploy mode) |

`token.json` must be produced by running `auth.py` on a machine with
a browser first — OAuth consent cannot run on a headless instance.
Make sure it authorizes the Google account you actually want to
search.

## 5. Create the pipeline job

**New Item → Pipeline**, then:

- **Definition:** Pipeline script from SCM
- **SCM:** Git
- **Repository URL:** `https://github.com/mohdkhan2406/Agent_mcp_gmail_gdrive.git`
- **Branch:** `*/main`
- **Script Path:** `Jenkinsfile`

Optionally tick **GitHub hook trigger for GITScm polling** and add a
webhook in the GitHub repo pointing at
`http://<EC2_PUBLIC_IP>:8080/github-webhook/`. This only works if
GitHub can reach port 8080 — which contradicts locking it to your
own IP. Prefer **Poll SCM** (`H/5 * * * *`) instead.

## 6. Build

**Build with Parameters:**

| Parameter | Value |
|---|---|
| `DEPLOY_MODE` | `local` |
| `REGISTRY_NAMESPACE` | your Docker Hub username |
| `PUSH_IMAGES` | ticked |
| `DEPLOY_HOST` | empty |

Run once with `DEPLOY_MODE=none` first to confirm the build and
smoke test pass before anything is deployed.

The app is then at `http://<EC2_PUBLIC_IP>/`.

## Ports

| Port | Service | Exposure |
|---|---|---|
| 80 | Frontend (nginx) | public |
| 8080 | Jenkins | your IP only |
| 8001 | Backend | loopback only — reached via `/api` |

## Troubleshooting

**`docker: 'compose' is not a docker command`** — `docker.io` was
installed instead of `docker-ce` + `docker-compose-plugin`. Re-run
the setup script.

**`permission denied ... /var/run/docker.sock`** — `jenkins` is not
in the `docker` group yet, or Jenkins was not restarted after
`usermod`. Run `sudo systemctl restart jenkins`.

**Frontend build killed during `npm run build`** — out of memory.
The instance is too small; use t3.small or larger.

**App says "Authorization needed"** — `token.json` is missing or
belongs to the wrong Google account. Check which:

```bash
docker exec agent-backend python -c "from mcp_server import get_drive_service; print(get_drive_service().about().get(fields='user(emailAddress)').execute())"
```

**Searches return nothing that should exist** — almost always the
wrong Google account rather than a code fault. Re-run `auth.py`,
pick the right account, update the `google-token-json` credential,
rebuild.
