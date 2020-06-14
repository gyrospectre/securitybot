#!/usr/bin/env bash

sudo apt update
sudo apt install -y python3-pip mysql-server libmariadbclient-dev

sudo mysql -u root < /vagrant/config/queries/db_server_init.sql

cd /vagrant
pip3 install -r requirements.txt
