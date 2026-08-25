# CI/CD

GitHub never SSHs into your Pi. The Pi runs a small agent (self-hosted runner) that **pulls** jobs. That works on any home Wi-Fi, no public IP.

```
you  --push-->  your fork (GitHub)
                    |
                    | job waiting for a runner labeled "raspi"
                    v
              your Pi (runner already connected)
                    |
                    v
         sync repo to DEPLOY_DIR + install wifi-fallback
```

Each person uses **their fork** and **their Pi**. Do not add a runner on the upstream repo ([spaguetti-nomad-pi/spaguetti-nomad-pi](https://github.com/spaguetti-nomad-pi/spaguetti-nomad-pi)).

The workflow only runs on forks. Defaults work with no edits (`DEPLOY_DIR=$HOME/spaguetti-nomad-pi`).

## 1. Fork

Fork [spaguetti-nomad-pi/spaguetti-nomad-pi](https://github.com/spaguetti-nomad-pi/spaguetti-nomad-pi).

## 2. Enable Actions on your fork

On **your fork** (not upstream):

1. **Settings → Actions → General** → allow Actions.
2. Under **Fork pull request workflows**, disable them or require approval. The runner is your computer; you do not want random PRs executing on it.
3. **Settings → Actions → Runners → New self-hosted runner**.
4. Choose Linux. Copy the **registration token** (not the commands). You will paste it on the Pi in step 4.

## 3. `cicd/deploy.env` (on the Pi)

This file stays on the Pi (gitignored). GitHub never reads it. It only tells the runner **where** to put the repo on disk.

```bash
cp cicd/deploy.env.example cicd/deploy.env
```

Leave it as-is unless you want another directory:

```bash
# cicd/deploy.env
DEPLOY_DIR=$HOME/spaguetti-nomad-pi
# REPO_URL=                    # empty = git remote origin (your fork)
RUNNER_LABEL=raspi             # must match .github/workflows/deploy.yml
```

Do not put SSH host, user, or passwords here. The Pi already has the code; the runner just updates that folder.

## 4. Register the runner (once, on the Pi)

SSH into the Pi, clone **your fork**, then install:

```bash
git clone git@github.com:<you>/spaguetti-nomad-pi.git ~/spaguetti-nomad-pi
cd ~/spaguetti-nomad-pi
git remote add upstream git@github.com:spaguetti-nomad-pi/spaguetti-nomad-pi.git

./cicd/install-runner.sh <token>
```

The script refuses to run if `origin` is the upstream repo.

In GitHub, **Settings → Actions → Runners**, the runner should show **Idle**.

## 5. Deploy

Push to `main` on **your fork** (or **Actions → Deploy → Run workflow**). The Pi must be on and online.

Pull new code from upstream:

```bash
git fetch upstream
git merge upstream/main
git push origin main
```
