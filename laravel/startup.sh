#!/bin/sh

AGENT_VERSION=0.8.4

apt-get update -y
add-apt-repository -y ppa:ondrej/php
apt install php8.1 php8.1-mcrypt unzip docker.io gosu openjdk-11-jre -y
adduser runops --system --group
curl -s -L https://github.com/runopsio/agent/releases/download/$AGENT_VERSION/agent-$AGENT_VERSION-standalone.jar > /opt/agent-standalone.jar
mv start-agent.sh /opt/start-agent.sh 
cd /opt/ && rm -rf example-app
curl -s https://laravel.build/example-app | bash
