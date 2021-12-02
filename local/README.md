# Agent Local

This examples demonstrate how to setup a runops agent locally for testing with local app system (e.g. postgres, python, etc).
It's useful for testing or development purposes to understand how the agent works and process tasks.

## Requirements

- Postgres local setup
- Python local setup
- [runops cli](https://www.npmjs.com/package/runops)
- java cli
- A user with permission to create **targets** and **tasks** in an organization on runops.
- An agent token with permission to run tasks

## Setup & Run

### Populate a local postgres database with data

```sh
psql -U <pg-user> -c "CREATE DATABASE worldtest"
psql -U <pg-user> worldtest < ./misc/world-db.sql
```

### Download the agent latest version and run it

```sh
AGENT_LATEST=$(curl -s https://api.github.com/repos/runopsio/agent/releases/latest |egrep "https://.+standalone.jar" |awk {'print $2'} |sed 's/"//g')
curl -sL $AGENT_LATEST > /tmp/agent-standalone.jar
export TOKEN=
export TAGS=local
export PG_CONFIG='{"PG_HOST": "127.0.0.1", "PG_USER": "<pg-user>", "PG_PASS": "123", "PG_DB": "worldtest", "PG_PORT": 5432}'
export APP_CONFIG='{"PYTHON_APP_ENV": "test-env"}'
java -jar /tmp/agent-standalone.jar
```

> In a production setup, the environment variables PG_CONFIG and APP_CONFIG could be used with a secret manager solution which is a more secure approach for sensitive content.

### Run postgres tasks

- Create a target

```sh
# the secret provider option will instruct the agent where to fetch for configuration
# and then inject in the runtime of the command - psql in this case.
runops targets create --name pglocal --type postgres --secret_provider env-var --secret_path PG_CONFIG --tags local
```

- Create a task which runs queries in your local postgres instance

```sh
runops tasks create --target pglocal -s 'SELECT code, name, continent, region, population, localname FROM country LIMIT 3'
code	name	continent	region	population	localname
AFG	Afghanistan	Asia	Southern and Central Asia	22720000	Afganistan/Afqanestan
NLD	Netherlands	Europe	Western Europe	15864000	Nederland
ANT	Netherlands Antilles	North America	Caribbean	217000	Nederlandse Antillen
(3 rows)
```

### Run python tasks

- Create a target

```sh
runops targets create --name pylocal --type python --secret_provider env-var --secret_path APP_CONFIG --tags local
```

- Create a task to run python scripts locally

```sh
runops tasks create --target pylocal -s 'print("Hello World From Runops")'
Hello World From Runops
```

- [Optional] Run tasks inside a runops REPL

```sh
runops tasks repl
REPL started, each command will be executed remotely
and displayed in this session. https://runops.io/docs/user-guides/REPL
Type :help to list available commands

=> :target pylocal
pylocal=>
#_=> import os
#_=> print(os.environ['PYTHON_APP_ENV'])
#_=>
test-env
```
