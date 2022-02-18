## Secret Manager

This script helps to automate the creation of users in MySQL and propagates then on [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/) and save the credentials for long term in the AWS Secret Manager.

### Configuration / Requirements

- A Kubernetes cluster with a valid Kubeconfig valid file
- MySQL user with permission to CREATE users and GRANT then permissions
- AWS Secret Manager credentials to create secrets
- [Helm 3](https://helm.sh/docs/intro/install/)

### Getting Started

1. Clone this repository

```sh
git clone git@github.com:runopsio/example-apps.git && cd example-apps/helpers
```

2. Generate a base64 kubeconfig file for a namespace, for testing purpose let's use the kubeconfig from a local installation

```sh
NAMESPACE=demo-sm
KUBECONFIG_DATA=$(kubectl config view -o json --minify --raw |jq . -c |base64)
```

To generate a Kubeconfig file from a service account, see [this gist](https://gist.github.com/innovia/fbba8259042f71db98ea8d4ad19bd708)

3. Deploy a MySQL instance in Kubernetes

```sh
kubectl create ns demo-sm
kubectl apply -n demo-sm -f ../kubernetes/mysql-deploy.yaml
```

4. Deploy an agent

```sh
LATEST_RELEASE=$(curl -s https://api.github.com/repos/runopsio/agent/releases/latest |jq .assets[1].browser_download_url -r)
# WARNING: If you have agents running in production, this operation will break then!
AGENT_TOKEN=$(runops agents create-token -f)
helm upgrade --install agent $LATEST_RELEASE \
    --set config.token=$AGENT_TOKEN \
    --set config.tags=dev \
    --set env_var[0].env=SECRET_MANAGER_CONFIG \
    --set env_var[0].vars.MYSQL_GRANT_USER=root \
    --set env_var[0].vars.MYSQL_GRANT_PASSWORD=1a2b3c4d \
    --set env_var[0].vars.MYSQL_GRANT_HOST=mysql.demo-sm \
    --set env_var[0].vars.MYSQL_GRANT_LIST="SELECT\,INSERT\,UPDATE\,CREATE" \
    --set env_var[0].vars.MYSQL_GRANT_DB=testdb \
    --set env_var[0].vars.AWS_ACCESS_KEY_ID= \
    --set env_var[0].vars.AWS_SECRET_ACCESS_KEY= \
    --set env_var[0].vars.AWS_DEFAULT_REGION= \
    --set env_var[0].vars.KUBECONFIG_DATA="$KUBECONFIG_DATA" \
    --set env_var[0].vars.SECRET_NAMESPACE=demo-sm \
    --set env_var[0].vars.AWS_SECRET_PREFIX=runops/dev/ \
    --set env_var[0].vars.KUBERNETES_SECRET_PREFIX=runops-dev- \
    --namespace demo-sm
```

5. Create a target

```sh
runops targets create --type python --name myapp-dev \
    --secret_provider env-var \
    --secret_path SECRET_MANAGER_CONFIG \
    --tags dev
```

6. Execute a task to create a new user on MySQL

The output will contain the name of the secret of the AWS secret manager and Kubernetes

```sh
runops tasks create -t myapp-dev -f ./secret-manager.py
```

7. Try to access the database with those credentials and create a table

```sh
kubectl port-forward -n demo-sm deploy/mysql 3306 3306
cat - > /tmp/create-table.sql <<EOF
CREATE TABLE IF NOT EXISTS tasks (
    task_id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    start_date DATE,
    due_date DATE,
    status TINYINT NOT NULL,
    priority TINYINT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)  ENGINE=INNODB;
EOF
MYSQL_USER=$(kubectl get secrets -n demo-sm -l managed-by=runops -o json  |jq '.items[0].data | .user |@base64d' -r)
MYSQL_PASS=$(kubectl get secrets -n demo-sm -l managed-by=runops -o json  |jq '.items[0].data | .password |@base64d' -r)

mysql -u$MYSQL_USER -p$MYSQL_PASS -D testdb -h 127.0.0.1 < /tmp/create-table.sql
mysql -u$MYSQL_USER -p$MYSQL_PASS -D testdb -h 127.0.0.1 -Bse "INSERT INTO tasks (title, status, priority) VALUES ('foo', 1, 1)"
mysql -u$MYSQL_USER -p$MYSQL_PASS -D testdb -h 127.0.0.1 -Bse "SELECT * FROM tasks"
1	foo	NULL	NULL	1	1	NULL	2022-02-18 21:19:53
mysql -u$MYSQL_USER -p$MYSQL_PASS -D testdb -h 127.0.0.1 -Bse "DELETE FROM tasks where title = 'foo'"
ERROR 1142 (42000) at line 1: DELETE command denied to user 'usr_7b1e36c36114'@'127.0.0.1' for table 'tasks'
```

So you can CREATE, INSERT and SELECT but not delete records.

8. Check if the secret manager has the stored credentials

```sh
# get the secret id in the logs of the task
aws secretsmanager describe-secret --secret-id <secret-id>
```

