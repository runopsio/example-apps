# README

This example demonstrate how to run a simple ruby on rails API application on Kubernetes and then interact with it via runops.

## Pre-requisites

- [rbenv](https://github.com/rbenv/rbenv)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)

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

This will use a pre-created app available on `runops/bandapi:latest` docker hub registry

```sh
# make sure to change the DOPPLER_TOKEN to a valid service account
kubectl apply -f ./k8s/
# create a k8s-exec type
runops targets create --name k8s-exec-local \
    --type k8s-exec \
    --secret_provider env-var \
    --secret_path ENV_CONFIG \
    --tags local
```

### Testing with runops / doppler

```sh
runops tasks create -t k8s-exec-local -s "deploy/bandapi doppler run -- rails db:migrate"
runops tasks create -t k8s-exec-local -s "deploy/bandapi doppler run -- rails runner 'Band.create(name: \"AC/DC\")'"
runops tasks create -t k8s-exec-local -s "deploy/bandapi doppler run -- rails runner 'Band.create(name: \"The Beatles\")'"
runops tasks create -t k8s-exec-local -s "deploy/bandapi curl http://127.0.0.1:3000/bands -s" |jq .
```

### Without Doppler

```sh
runops tasks create -t k8s-exec-local -s "deploy/bandapi rails db:migrate"
runops tasks create -t k8s-exec-local -s "deploy/bandapi rails runner 'Band.create(name: \"AC/DC\")'"
runops tasks create -t k8s-exec-local -s "deploy/bandapi rails runner 'Band.create(name: \"The Beatles\")'"
runops tasks create -t k8s-exec-local -s "deploy/bandapi curl http://127.0.0.1:3000/bands -s" |jq .
```
