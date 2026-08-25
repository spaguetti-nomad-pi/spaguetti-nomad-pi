# Load cicd/deploy.env from the Pi-local copy, then the repo copy.

CICD_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$CICD_DIR/.." && pwd)

# shellcheck disable=SC1091
source "$CICD_DIR/upstream.env"

_cicd_source() {
  local f=$1
  [[ -n $f && -f $f ]] || return 0
  # shellcheck disable=SC1090
  source "$f"
}

_cicd_norm_repo_url() {
  local u=${1%/}
  u=${u%.git}
  echo "$u" | tr '[:upper:]' '[:lower:]'
}

_cicd_source "${HOME}/.config/raspi/deploy.env"
_cicd_source "${REPO_ROOT}/cicd/deploy.env"

DEPLOY_DIR=${DEPLOY_DIR:-$HOME/spaguetti-nomad-pi}
_cicd_source "${DEPLOY_DIR}/cicd/deploy.env"

DEPLOY_DIR=${DEPLOY_DIR:-$HOME/spaguetti-nomad-pi}
RUNNER_LABEL=${RUNNER_LABEL:-raspi}
RUNNER_DIR=${RUNNER_DIR:-$HOME/actions-runner}
RUNNER_NAME=${RUNNER_NAME:-$(hostname -s 2>/dev/null || hostname)}

if [[ -z ${REPO_URL:-} ]]; then
  remote=$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || true)
  remote=${remote%.git}
  case $remote in
    git@github.com:*)
      REPO_URL="https://github.com/${remote#git@github.com:}"
      ;;
    ssh://git@github.com/*)
      REPO_URL="https://github.com/${remote#ssh://git@github.com/}"
      ;;
    https://github.com/*)
      REPO_URL=$remote
      ;;
    *)
      REPO_URL=""
      ;;
  esac
fi
