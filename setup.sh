#!/bin/bash

# --- НАСТРОЙКИ ---
PYTHON_VERSION="3.12.3"
GITHUB_REPO="https://github.com/totodiemono/Starvell-Tipzy.git"
PROJECT_DIR="Starvell-Tipzy"
SERVICE_NAME="starvell-tipzy"
BOT_FILE="bot.py"
# -----------------

LIGHTBLUE='\033[1;94m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

clear

echo -e "${LIGHTBLUE}"
cat << "EOF"
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
Лучшие плагины - https://t.me/tipzymarket_bot
EOF
echo -e "${NC}"

echo -e "${LIGHTBLUE}[Starvell-Tipzy] Начинаю установку (Systemd Version)...${NC}"


echo -e "${LIGHTBLUE}[1/6] Установка системных зависимостей...${NC}"
sudo apt-get update -qq > /dev/null
sudo apt-get install -y wget build-essential libncursesw5-dev libssl-dev \
libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev git > /dev/null
echo -e "${GREEN}✓ Зависимости установлены${NC}"

if ! command -v python3.12 &> /dev/null; then
    echo -e "${LIGHTBLUE}[2/6] Python 3.12 не найден. Сборка из исходников (5-10 мин)...${NC}"
    cd /tmp
    wget -q https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz
    tar xzf Python-${PYTHON_VERSION}.tgz
    cd Python-${PYTHON_VERSION}
    ./configure --enable-optimizations > /dev/null
    make -j$(nproc) > /dev/null 
    sudo make altinstall > /dev/null
    cd ..
    sudo rm -rf Python-${PYTHON_VERSION} Python-${PYTHON_VERSION}.tgz
    echo -e "${GREEN}✓ Python ${PYTHON_VERSION} установлен${NC}"
else
    echo -e "${GREEN}[2/6] Python 3.12 уже на месте.${NC}"
fi

cd ~

echo -e "${LIGHTBLUE}[3/6] Проверка репозитория...${NC}"
if [ -d "$PROJECT_DIR" ]; then
    echo -e "Папка есть. Делаем git pull..."
    cd "$PROJECT_DIR"
    git pull
else
    echo -e "Клонирую репозиторий..."
    git clone "$GITHUB_REPO" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi
echo -e "${GREEN}✓ Файлы получены${NC}"

WORK_DIR=$(pwd)
CURRENT_USER=$(whoami)

echo -e "${LIGHTBLUE}[4/6] Настройка .venv...${NC}"
rm -rf .venv
/usr/local/bin/python3.12 -m venv .venv
VENV_PYTHON="$WORK_DIR/.venv/bin/python"
VENV_PIP="$WORK_DIR/.venv/bin/pip"

$VENV_PIP install --upgrade pip -q
echo -e "${GREEN}✓ Виртуальное окружение готово${NC}"


if [ -f "requirements.txt" ]; then
    echo -e "${LIGHTBLUE}[5/6] Скачивание библиотек...${NC}"
    echo -e "${LIGHTBLUE}bash скрипт делал -> t.me/yusxe :)${NC}"
    $VENV_PIP install -r requirements.txt
    echo -e "${GREEN}✓ Библиотеки установлены${NC}"
else
    echo -e "${RED}x Файл requirements.txt не найден!${NC}"
fi


echo -e "${LIGHTBLUE}[6/6] Создание службы systemd (${SERVICE_NAME})...${NC}"

sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOL
[Unit]
Description=Starvell-Tipzy Bot Service
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${WORK_DIR}
ExecStart=${VENV_PYTHON} ${WORK_DIR}/${BOT_FILE}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL

echo -e "Обновление демона systemd..."
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
echo -e "Перезапуск службы..."
sudo systemctl restart ${SERVICE_NAME}

echo -e ""
echo -e "${LIGHTBLUE}[Starvell-Tipzy]${NC} ${GREEN}[SUCCESS]${NC} -> Бот запущен как сервис!"
echo -e "---------------------------------------------------------"
echo -e "Статус бота:    ${LIGHTBLUE}sudo systemctl status ${SERVICE_NAME}${NC}"
echo -e "Смотреть логи:  ${LIGHTBLUE}journalctl -u ${SERVICE_NAME} -f${NC}"
echo -e "Остановить:     ${LIGHTBLUE}sudo systemctl stop ${SERVICE_NAME}${NC}"
echo -e "Запустить:      ${LIGHTBLUE}sudo systemctl start ${SERVICE_NAME}${NC}"
echo -e "---------------------------------------------------------"