#!/usr/bin/env bash
set -euo pipefail

PYTHON_VERSION="${PYTHON_VERSION:-3.11}"
PYTHON_PATCH="${PYTHON_PATCH:-3.11.9}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="${REPO_ROOT}/.venv"

log() { printf "[bootstrap] %s\n" "$*"; }
command_exists() { command -v "$1" >/dev/null 2>&1; }

python_matches() {
  local cmd="$1"
  "$cmd" - <<PY
import sys
required = "${PYTHON_VERSION}"
major, minor = map(int, required.split(".")[:2])
version = sys.version_info
sys.exit(0 if (version.major == major and version.minor == minor) else 1)
PY
}

find_compatible_python() {
  local candidates=("python${PYTHON_VERSION}" "python${PYTHON_VERSION%.*}" python3 python)
  for candidate in "${candidates[@]}"; do
    if command_exists "$candidate" && python_matches "$candidate"; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

install_with_pyenv() {
  if ! command_exists pyenv; then
    return 1
  fi

  log "Installing Python ${PYTHON_PATCH} via pyenv..."
  pyenv install -s "${PYTHON_PATCH}"
  local pyenv_root
  pyenv_root="$(pyenv root)"
  local py_path="${pyenv_root}/versions/${PYTHON_PATCH}/bin/python3"
  if [[ -x "$py_path" ]]; then
    echo "$py_path"
    return 0
  fi
  return 1
}

install_with_apt() {
  if ! command_exists apt-get; then
    return 1
  fi

  local sudo_prefix=""
  if [[ "$EUID" -ne 0 ]] && command_exists sudo; then
    sudo_prefix="sudo "
  fi

  log "Installing Python ${PYTHON_VERSION} via apt-get..."
  ${sudo_prefix}apt-get update
  ${sudo_prefix}apt-get install -y "python${PYTHON_VERSION}" "python${PYTHON_VERSION}-venv"

  if command_exists "python${PYTHON_VERSION}"; then
    echo "$(command -v "python${PYTHON_VERSION}")"
    return 0
  fi
  return 1
}

install_python() {
  local installer
  for installer in install_with_pyenv install_with_apt; do
    if python_path="$($installer)"; then
      echo "$python_path"
      return 0
    fi
  done

  log "Could not auto-install Python ${PYTHON_VERSION}. Please install it manually and rerun this script."
  return 1
}

ensure_python() {
  if python_path="$(find_compatible_python)"; then
    log "Using existing Python interpreter: ${python_path}"
    echo "$python_path"
    return 0
  fi

  log "No compatible Python ${PYTHON_VERSION} interpreter found. Attempting installation..."
  python_path="$(install_python)" || exit 1
  log "Installed Python at ${python_path}"
  echo "$python_path"
}

create_venv() {
  local python_path="$1"
  if [[ ! -d "$VENV_PATH" ]]; then
    log "Creating virtual environment at ${VENV_PATH}"
    "$python_path" -m venv "$VENV_PATH"
  else
    log "Reusing existing virtual environment at ${VENV_PATH}"
  fi
}

install_requirements() {
  source "${VENV_PATH}/bin/activate"
  log "Upgrading pip"
  python -m pip install --upgrade pip
  log "Installing dependencies from requirements.txt"
  python -m pip install -r "${REPO_ROOT}/requirements.txt"
}

main() {
  log "Bootstrapping DayZ Death Watcher"
  local python_path
  python_path="$(ensure_python)"
  create_venv "$python_path"
  install_requirements
  log "Environment ready. Activate it with: source ${VENV_PATH}/bin/activate"
  log "Then run the bot with: python main.py"
}

main "$@"
