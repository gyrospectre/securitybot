sudo apt install -y docker.io docker-compose
export VAULT_TOKEN_ID=`openssl rand -base64 32`
sudo --preserve-env=VAULT_TOKEN_ID docker-compose up -d
sleep 5
python3 init.py
