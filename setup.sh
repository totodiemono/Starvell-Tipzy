#!/bin/bash

PYTHON_VERSION="3.12.3"
GITHUB_REPO="https://github.com/totodiemono/Starvell-Tipzy.git"
PROJECT_DIR="Starvell-Tipzy"
SERVICE_NAME="starvell-tipzy"
BOT_FILE="bot.py"

LIGHTBLUE='\033[1;94m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
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

echo -e "${LIGHTBLUE}[Starvell-Tipzy] Начинаю установку...${NC}"

sudo apt-get update -qq > /dev/null
sudo apt-get install -y wget build-essential libncursesw5-dev libssl-dev \
libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev git > /dev/null

if ! command -v python3.12 &> /dev/null; then
    echo -e "${LIGHTBLUE}Установка Python 3.12 (5-10 мин)...${NC}"
    cd /tmp
    wget -q https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz
    tar xzf Python-${PYTHON_VERSION}.tgz
    cd Python-${PYTHON_VERSION}
    ./configure --enable-optimizations > /dev/null
    make -j$(nproc) > /dev/null 
    sudo make altinstall > /dev/null
    cd ..
    sudo rm -rf Python-${PYTHON_VERSION} Python-${PYTHON_VERSION}.tgz
    echo -e "${GREEN}✓ Python установлен${NC}"
else
    echo -e "${GREEN}✓ Python уже установлен${NC}"
fi

cd ~

if [ -d "$PROJECT_DIR" ]; then
    cd "$PROJECT_DIR"
    git pull
else
    git clone "$GITHUB_REPO" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

WORK_DIR=$(pwd)
CURRENT_USER=$(whoami)

rm -rf .venv
/usr/local/bin/python3.12 -m venv .venv
VENV_PYTHON="$WORK_DIR/.venv/bin/python"
VENV_PIP="$WORK_DIR/.venv/bin/pip"

$VENV_PIP install --upgrade pip -q

if [ -f "requirements.txt" ]; then
    echo -e "${LIGHTBLUE}Установка библиотек...${NC}"
    $VENV_PIP install -r requirements.txt
    echo -e "${GREEN}✓ Библиотеки установлены${NC}"
else
    echo -e "${RED}x Файл requirements.txt не найден!${NC}"
fi

echo -e ""
echo -e "${YELLOW}===========================================${NC}"
echo -e "${YELLOW}   РЕЖИМ НАСТРОЙКИ${NC}"
echo -e "${YELLOW}===========================================${NC}"
echo -e "1. Следуйте инструкции после запуска скрипта."
echo -e "2. Когда настройка завершится, нажмите ${RED}Ctrl + C${NC} для запуска фоновой службы."
echo -e ""
read -p "Нажмите ENTER, чтобы начать настройку..."

$VENV_PYTHON $BOT_FILE

echo -e ""
echo -e "${GREEN}✓ Конфиг сохранен.${NC}"
echo -e "${LIGHTBLUE}Создание службы systemd...${NC}"

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

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}

echo -e ""
echo -e "${LIGHTBLUE}[Starvell-Tipzy]${NC} ${GREEN}[УСПЕХ]${NC} -> Служба запущена!"
echo -e "Логи:       ${LIGHTBLUE}journalctl -u ${SERVICE_NAME} -f${NC}"
echo -e "Остановить: ${LIGHTBLUE}sudo systemctl stop ${SERVICE_NAME}${NC}"