#!/bin/sh

AGENT_LATEST=$(curl -s https://api.github.com/repos/runopsio/agent/releases/latest |egrep "https://.+standalone.jar" |awk {'print $2'} |sed 's/"//g')

apt-get update -y
add-apt-repository -y ppa:ondrej/php
apt install php8.1 php8.1-mcrypt unzip docker.io gosu openjdk-11-jre -y
adduser runops --system --group
curl -sL $AGENT_LATEST > /opt/agent-standalone.jar
mv start-agent.sh /opt/start-agent.sh 
cd /opt/ && rm -rf example-app
curl -s https://laravel.build/example-app | bash
