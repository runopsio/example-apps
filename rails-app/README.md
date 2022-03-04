# README

This example demonstrate how to run a simple ruby on rails API application on Kubernetes and then interact with it via runops.

## Pre-requisites

- [rbenv](https://github.com/rbenv/rbenv)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [runops cli](https://runops.io/docs/developers/)

## Setup

```sh
rbenv local 3.0.3
rails new . --api
rails g scaffold Band name:string
cat - > Dockerfile <<EOF
FROM ruby:3.0.3
RUN apt-get update && \
    apt-get install -y apt-transport-https ca-certificates curl gnupg && \
    curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | apt-key add - && \
    echo "deb https://packages.doppler.com/public/cli/deb/debian any-version main" | tee /etc/apt/sources.list.d/doppler-cli.list && \
    apt-get update && \
    apt-get install -y doppler
WORKDIR /myapp
ENV RAILS_ENV=development

COPY Gemfile /myapp/Gemfile
COPY Gemfile.lock /myapp/Gemfile.lock
RUN bundle install
COPY . /myapp

EXPOSE 3000

# Start the main process.
CMD ["rails", "server", "-b", "0.0.0.0"]
EOF
```

## Testing locally

```sh
docker build -t bandapi .
docker run --rm -it -p 3000:3000 --name bandapi bandapi
docker exec -it bandapi rails db:migrate
docker exec -it bandapi rails runner 'Band.create(name: "AC/DC")'
docker exec -it bandapi rails runner 'Band.create(name: "The Beatles")'
curl -s http://localhost:3000/bands |jq .
```

## Testing with runops

1. [Deploy an agent](https://github.com/runopsio/agent/tree/main/setup) with access to a Kubernetes instance (it could be local or in the cloud)

Create an **env-var** configuration with the following values and deploy the agent (please refer to the agent setup instructions)

```sh
KUBECONFIG_DATA=$(kubectl config view -o json --minify --raw |jq . -c |base64)
export ENV_CONFIG=`cat - <<EOF
{
  "KUBE_CONFIG_DATA": "$KUBECONFIG_DATA",
  "K8S_EXEC_COMMAND": "doppler run -- rails runner -",
  "K8S_EXEC_RESOURCE": "deploy/bandapi"
}
EOF
`
<script-to-deploy-agent>
```

> This example uses doppler, but you could remove it and run it as `rails runner -`

2. Deploy the rails app and create a target

> This guide uses a pre-created app available on `runops/bandapi:latest` docker hub registry

```sh
# make sure to change the DOPPLER_TOKEN to a valid service account
kubectl apply -f ./k8s/
# create a k8s-exec type
runops targets create --name k8s-exec-rails \
    --type k8s-exec \
    --secret_provider env-var \
    --secret_path ENV_CONFIG \
    --tags local
```

### Running scripts from k8s-exec directly

```sh
# inline execution
runops tasks create -t k8s-exec-rails -s "puts 123"
# runs as a script
cat - > /tmp/script.rb <<EOF
require 'base64'
print(Base64.decode64('aGVsbG93b3JsZAo'))
EOF
runops tasks create -t k8s-exec-rails -f /tmp/script.rb
```

### Running bash commands

In order for this to work, remove the env vars `K8S_EXEC_COMMAND` and `K8S_EXEC_RESOURCE` from the env-config and restart the agent.

```sh
runops tasks create -t k8s-exec-rails -s "deploy/bandapi doppler run -- rails db:migrate"
runops tasks create -t k8s-exec-rails -s "deploy/bandapi doppler run -- rails runner 'Band.create(name: \"AC/DC\")'"
runops tasks create -t k8s-exec-rails -s "deploy/bandapi doppler run -- rails runner 'Band.create(name: \"The Beatles\")'"
runops tasks create -t k8s-exec-rails -s "deploy/bandapi curl http://127.0.0.1:3000/bands -s" |jq .
```
