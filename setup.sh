#!/usr/bin/env bash

set -euo pipefail

readonly PYTHON_VERSION="3.12.3"
readonly PYTHON_BIN="python3.12"
readonly PYTHON_INSTALL_DIR="/usr/local/bin/${PYTHON_BIN}"
readonly GITHUB_REPO="https://github.com/totodiemono/Starvell-Tipzy.git"
readonly PROJECT_DIR="Starvell-Tipzy"
readonly SERVICE_NAME="starvell-tipzy"
readonly BOT_FILE="bot.py"

readonly BLUE='\033[1;94m'
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[1;33m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

info()    { echo -e "${BLUE}[Starvell-Tipzy]${NC} $*"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
warn()    { echo -e "${YELLOW}⚠${NC} $*"; }
fail()    { echo -e "${RED}✗${NC} $*" >&2; }

die() {
    fail "$@"
    exit 1
}

banner() {
    echo -e "${BLUE}"
    cat << "BANNER"
                              ████████
                             ███████████
                            ███████████████                     ██████████
                            █████████████████               ████████████████
                            ████████████████████        ████████████████████
                            ██████████████████████   ███████████████████████
                            ████████████████████████████████████████████████
                             ███████████████████████████████████████████████
                             ██████████████████████████████████████████████
                             ██████████████████████████████████████████████
                             █████████████████████████████████████████████
                             ███████████████████████████████████████████
                              █████████████████████████████████████████
                             █████████████████████████████████████████
                         ███████████████████████████████████████████
                      █████████████████████████████████████████████
                   ██████████████████████████████████████████████
                 █████████████████████████████████████████████
               ██████████████████████████████████████████████
              ████████████████████████████████████████████           ██████████
             ██████████████████████████████████████████         ██████████████████
             ███████████████████████████████████████         ███████████████████████
             ███████████████████████████████████          ███████████████████████████
              ██████████████████████████████           ███████████████████████████████
               █████████████████████████            ███████████████████████████████████
                   ███████████████              ████████████████████████████████████████
                                             ███████████████████████████████████████████
                                           █████████████████████████████████████████████
                                         ███████████████████████████████████████████████
                                        ███████████████████████████████████████████████
                                      ███████████████████████████████████████████████
                                      ████████████████████████
                                     ████████████████████████
                                     ███████████████████████
                                     ██████████████████████
                                      ████████████████████
                                      ███████████████████
                                       █████████████████
                                        ███████████████
                                         █████████████
                                          ██████████
                                            ██████
  Лучшие плагины — https://t.me/tipzymarket_bot
BANNER
    echo -e "${NC}"
}

check_os() {
    if [[ ! -f /etc/debian_version ]]; then
        warn "Скрипт рассчитан на Debian/Ubuntu. На вашей ОС могут быть проблемы."
    fi
}

check_sudo() {
    if ! sudo -n true 2>/dev/null; then
        info "Для установки потребуются права sudo."
    fi
}

install_system_deps() {
    info "Обновление пакетов и установка системных зависимостей..."
    sudo apt-get update -qq > /dev/null 2>&1
    sudo apt-get install -y -qq \
        wget build-essential libncursesw5-dev libssl-dev \
        libsqlite3-dev tk-dev libgdbm-dev libc6-dev \
        libbz2-dev libffi-dev zlib1g-dev git > /dev/null 2>&1
    success "Системные зависимости установлены"
}

install_python() {
    if command -v "$PYTHON_BIN" &> /dev/null; then
        success "Python 3.12 уже установлен ($(${PYTHON_BIN} --version 2>&1))"
        return
    fi

    info "Установка Python ${PYTHON_VERSION} (сборка из исходников, 5-10 мин)..."
    (
        cd /tmp
        wget -q "https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"
        tar xzf "Python-${PYTHON_VERSION}.tgz"
        cd "Python-${PYTHON_VERSION}"
        ./configure --enable-optimizations > /dev/null 2>&1
        make -j"$(nproc)" > /dev/null 2>&1
        sudo make altinstall > /dev/null 2>&1
    )
    sudo rm -rf "/tmp/Python-${PYTHON_VERSION}" "/tmp/Python-${PYTHON_VERSION}.tgz"

    if command -v "$PYTHON_BIN" &> /dev/null; then
        success "Python ${PYTHON_VERSION} установлен"
    else
        die "Не удалось установить Python ${PYTHON_VERSION}"
    fi
}

setup_repo() {
    cd ~

    if [[ -d "$PROJECT_DIR" ]]; then
        info "Обновление репозитория..."
        cd "$PROJECT_DIR"
        git pull --ff-only || git pull
    else
        info "Клонирование репозитория..."
        git clone "$GITHUB_REPO" "$PROJECT_DIR"
        cd "$PROJECT_DIR"
    fi

    success "Репозиторий готов"
}

setup_venv() {
    local work_dir="$1"

    info "Создание виртуального окружения..."
    rm -rf .venv
    "${PYTHON_INSTALL_DIR}" -m venv .venv

    local venv_pip="${work_dir}/.venv/bin/pip"
    "${venv_pip}" install --upgrade pip -q > /dev/null 2>&1

    if [[ -f "requirements.txt" ]]; then
        info "Установка библиотек..."
        "${venv_pip}" install -r requirements.txt -q
        success "Библиотеки установлены"
    else
        die "Файл requirements.txt не найден!"
    fi
}

run_initial_setup() {
    local venv_python="$1"

    echo ""
    echo -e "${YELLOW}===========================================${NC}"
    echo -e "${YELLOW}   РЕЖИМ НАСТРОЙКИ${NC}"
    echo -e "${YELLOW}===========================================${NC}"
    echo -e "1. Следуйте инструкции после запуска скрипта."
    echo -e "2. Когда настройка завершится, нажмите ${RED}Ctrl+C${NC} для запуска фоновой службы."
    echo ""
    read -rp "Нажмите ENTER, чтобы начать настройку..."

    trap 'echo ""; success "Конфиг сохранён."' INT
    "${venv_python}" "$BOT_FILE" || true
    trap - INT
}

create_service() {
    local work_dir="$1"
    local venv_python="$2"
    local current_user
    current_user="$(whoami)"

    info "Создание службы systemd..."

    sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" > /dev/null <<EOF
[Unit]
Description=Starvell-Tipzy Bot Service
After=network.target

[Service]
Type=simple
User=${current_user}
WorkingDirectory=${work_dir}
ExecStart=${venv_python} ${work_dir}/${BOT_FILE}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable "${SERVICE_NAME}" > /dev/null 2>&1
    sudo systemctl restart "${SERVICE_NAME}"

    echo ""
    success "${BOLD}Служба запущена!${NC}"
    echo ""
    echo -e "  Логи:        ${BLUE}journalctl -u ${SERVICE_NAME} -f${NC}"
    echo -e "  Остановить:  ${BLUE}sudo systemctl stop ${SERVICE_NAME}${NC}"
    echo -e "  Перезапуск:  ${BLUE}sudo systemctl restart ${SERVICE_NAME}${NC}"
    echo -e "  Статус:      ${BLUE}sudo systemctl status ${SERVICE_NAME}${NC}"
    echo ""
}

main() {
    clear
    banner

    check_os
    check_sudo
    install_system_deps
    install_python
    setup_repo

    local work_dir
    work_dir="$(pwd)"
    local venv_python="${work_dir}/.venv/bin/python"

    setup_venv "$work_dir"
    run_initial_setup "$venv_python"
    create_service "$work_dir" "$venv_python"
}

main "$@"
