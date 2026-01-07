#!/bin/bash

PYTHON_VERSION="3.12.3"
GITHUB_REPO="https://github.com/totodiemono/Starvell-Tipzy.git"
PROJECT_DIR="Starvell-Tipzy"
SCREEN_NAME="Starvell-Tipzy"
BOT_FILE="bot.py"

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

echo -e "${LIGHTBLUE}[Starvell-Tipzy] Начинаю установку...${NC}"

echo -e "${LIGHTBLUE}[1/6] Установка системных зависимостей...${NC}"
sudo apt-get update -qq > /dev/null
sudo apt-get install -y wget build-essential libncursesw5-dev libssl-dev \
libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev git screen > /dev/null
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
    echo -e "Папка есть."
    cd "$PROJECT_DIR"
else
    echo -e "Клонирую репозиторий..."
    git clone "$GITHUB_REPO" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi
echo -e "${GREEN}✓ Файлы получены${NC}"

echo -e "${LIGHTBLUE}[4/6] Настройка .venv...${NC}"
/usr/local/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
echo -e "${GREEN}✓ Виртуальное окружение готово${NC}"

if [ -f "requirements.txt" ]; then
    echo -e "${LIGHTBLUE}[5/6] Скачивание библиотек (pip install)...${NC}"
    echo -e "${LIGHTBLUE}bash скрипт делал -> t.me/yusxe :)${NC}"
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Библиотеки установлены${NC}"
else
    echo -e "${RED}x Файл requirements.txt не найден!${NC}"
fi

echo -e "${LIGHTBLUE}[6/6] Перезапуск бота в screen...${NC}"
screen -X -S "$SCREEN_NAME" quit 2>/dev/null
screen -dmS "$SCREEN_NAME" bash -c "source $(pwd)/.venv/bin/activate; python $BOT_FILE; exec bash"

echo -e ""

echo -e "${LIGHTBLUE}[Starvell-Tipzy]${NC} ${GREEN}[SUCCESS]${NC} -> Успешная установка! Следуйте инструкции ниже ↓"

echo -e "Вход в консоль: ${LIGHTBLUE}screen -r $SCREEN_NAME${NC}"
echo -e "Выход (оставить рабочим): ${LIGHTBLUE}Ctrl+A, D${NC}"