# Kubernetes

This examples demonstrate how to setup a runops agent on a Kubernetes cluster and execute tasks inside a MySQL database and execute python script tasks connecting in this database.

## Requirements

- Kubernetes Cluster
- [runops cli](https://www.npmjs.com/package/runops)
- A user with permission to create **targets** and **tasks** in an organization on runops.
- An agent token with permission to run tasks

## Setup & Run

```sh
# deploy the agent inside the runops namespace
export AGENT_TOKEN= #-- change-me --#
export ENV_CONFIG=`cat - <<EOF
{
  "MYSQL_HOST": "mysql",
  "MYSQL_USER": "root",
  "MYSQL_PASS": "1a2b3c4d",
  "MYSQL_PORT": "3306",
  "MYSQL_DB": "testdb"
}
EOF`
curl -sL https://raw.githubusercontent.com/runopsio/agent/main/setup/k8s.sh | bash

# deploy a mysql instance inside the runops namespace 
kubectl apply -n runops -f ./mysql-deploy.yaml
```

### Run a MySQL tasks

- Create a target

```sh
runops targets create \
    --name my-test-db \
    --type mysql \
    --secret_provider 'env-var' \
    --secret_path 'ENV_CONFIG'
```

- Create a task which runs queries in the MySQL instance

```sh
runops tasks create --target my-test-db -s 'SELECT NOW()'
NOW()
2021-12-03 19:18:58
```

### Run a python task which connects to the MySQL instance

```sh
cat - > /tmp/test-conn.py <<EOF
import pymysql.cursors

# Connect to the database
connection = pymysql.connect(host='mysql',
                             user='root',
                             password='1a2b3c4d',
                             database='testdb',
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor)

with connection:
    with connection.cursor() as cursor:
        # Read a single record
        sql = "SELECT NOW()"
        cursor.execute(sql)
        result = cursor.fetchone()
        print(result)
EOF

runops tasks create --target my-test-db --type python -f /tmp/test-conn.py
```
