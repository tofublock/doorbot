# Doorbot

Telegram bot to remotely open your house door with simple user management, access restrictions and access log.


## Requirements

- Raspberry Pi 3 or 4
- Relais connected to your house intercom's open button hooked up to a GPIO pin on your Raspberry Pi (DO THIS AT YOUR OWN RISK!).


## Installation
1. Install Docker

    curl -fsSL https://get.docker.com -o get-docker.sh
    
    sudo sh get-docker.sh
    
    sudo usermod -aG docker <your-user>

2. Install Docker Compose

    sudo apt update && sudo apt install -y libffi-dev libssl-dev python3 python3-pip
    
    sudo apt install docker-compose

3. Clone repo
    sudo apt update && sudo apt install git
    
    git clone https://github.com/tofublock/doorbot.git
    
    cd doorbot
    
4. Acquire bot secret and admin user ID

     - Send /start to @BotFather on Telegram, create a new bot and take note of the BOT API SECRET
     - Send /start to @userinfobot on Telegram and take note of your user ID

5. Adapt `docker-compose.yaml` - secret, pin, and at least one user ID need to be set! If you want more users to be admins separate them with semicolons.

    - TG-SECRET: "BOT-SECRET"
    - PIN: 21
    - ADMINS: "USERID1;USERID2;..."

6. Spin up docker containers

    docker-compose up -d

7. Talk to your bot
    - Send /start to your bot to get going
    - Share a contact with the bot to add this user to the user list
