# Copyright (c) Runops Inc
# https://runops.io
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

#!/usr/bin/env python
import boto3
import random
import string
import secrets
import logging
import json
import sys
import base64
import time
import tempfile
import os
import re
from sqlalchemy import create_engine
from kubernetes import client, config

"""
Creates a MySQL random user with secure random password and
store in AWS Secret Manager and Kubernetes Secrets.
In order to run this script check the required environment variables
needed to run this script.

To run this script the following dependencies are required:

- A valid kubernetes config file
- A MySQL admin credentials to create users and grant permissions
- Secret manager access to create secrets

This script could be used in multiple environments using Runops, check
more instructions on README.md.
"""

logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s  %(name)s %(levelname)s - %(message)s',
        stream=sys.stdout,
        datefmt="%Y-%m-%dT%H:%M:%S%z")
log = logging.getLogger(__name__)

REQUIRED_ENVIRONMENTS = {
    # required for creating and granting new users permissions in a database
    'MYSQL_GRANT_USER': 'required',
    'MYSQL_GRANT_PASSWORD': 'required',
    'MYSQL_GRANT_HOST': 'required',
    'MYSQL_GRANT_DB': 'required',
    'MYSQL_GRANT_LIST': 'required',

    # required for acessing the AWS Secret Manager and storing
    # the credentials of new MySQL users
    'AWS_ACCESS_KEY_ID': 'required',
    'AWS_SECRET_ACCESS_KEY': 'required',
    'AWS_DEFAULT_REGION': 'required',

    # [OPTIONAL] it will be used as prefix name to AWS secret manager and Kubernetes.
    # AWS Secret Prefix must contain only alphanumeric characters and the characters /_+=.@- 
    'AWS_SECRET_PREFIX': 'optional',
    'KUBERNETES_SECRET_PREFIX': 'optional',
    
    # required for creating Kubernetes Secrets containing
    # the credentials of MySQL users. It should be a base64 kubeconfig file
    'KUBECONFIG_DATA': 'required',
    # the namespace to create the secret.
    'SECRET_NAMESPACE': 'required',
}
REQUIRED_ENVIRONMENTS_LIST = REQUIRED_ENVIRONMENTS.keys()
MYSQL_GRANT_ALLOWED_LIST = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE',
    'DROP', 'RELOAD', 'PROCESS', 'REFERENCES', 'INDEX', 'ALTER', 'SHOW DATABASES',
    'CREATE TEMPORARY TABLES', 'LOCK TABLES', 'EXECUTE', 'REPLICATION SLAVE',
    'REPLICATION CLIENT', 'CREATE VIEW', 'SHOW VIEW', 'CREATE ROUTINE', 
    'ALTER ROUTINE', 'CREATE USER', 'EVENT']

def parse_runtime_credentials():
    """
    Will parse the runtime credentials required to run this program
    and validate if all environments are present.
    """
    for env in REQUIRED_ENVIRONMENTS_LIST:
        if env not in os.environ and REQUIRED_ENVIRONMENTS[env] == 'required':
            return None, 'Missing required environment variable {}'.format(env)
    
    for grant in os.environ['MYSQL_GRANT_LIST'].split(','):
        if grant not in MYSQL_GRANT_ALLOWED_LIST:
            return None, 'MySQL Grant not allowed, found={}, allowed={}'.format(
                grant, ','.join(MYSQL_GRANT_ALLOWED_LIST),
            )

    k8s_secret_prefix = os.environ.get('KUBERNETES_SECRET_PREFIX', 'runops-')
    if k8s_secret_prefix:
        if len(k8s_secret_prefix) > 20:
            return None, 'KUBERNETES_SECRET_PREFIX reach max length size (20)'
        if re.search('^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$', k8s_secret_prefix):
            return None, 'KUBERNETES_SECRET_PREFIX contains unsupported characteres'

    aws_secret_prefix = os.environ.get('AWS_SECRET_PREFIX', 'runops/')
    if aws_secret_prefix:
        if len(aws_secret_prefix) > 150:
            return None, 'AWS_SECRET_PREFIX reach max length size (150)'

    # populate defaults
    os.environ['KUBERNETES_SECRET_PREFIX'] = k8s_secret_prefix
    os.environ['AWS_SECRET_PREFIX'] = aws_secret_prefix

    return dict(map(lambda e: (e, os.environ[e]), REQUIRED_ENVIRONMENTS_LIST)), None

def get_sm_cred(secret_name):
    try:
        client = boto3.client('secretsmanager')
        resp = client.get_secret_value(SecretId=secret_name)
        print(resp)
        return {'ARN': resp['ARN'],
                'Name': resp['Name'], 
                'VersionId': resp['VersionId'], 
                'SecretString': resp['SecretString'],
                'VersionStages': resp['VersionStages']}, None
    except Exception as ex:
        return None, e

def random_password(password_lenght=25):
    options = string.ascii_lowercase + string.ascii_uppercase
    options += string.digits + '_&#-<>=+|~^*'
    return ''.join(random.sample(options, password_lenght))

def random_credentials():
    return 'usr_' + ''.join(secrets.token_hex(6)), random_password()

def generate_secret_name(secret_prefix, secret_suffix):
    return secret_prefix + secret_suffix

def create_db_user(runtime_cred, grant_list):
    conn_string = 'mysql+pymysql://{user}:{password}@{host}:3306'.format(
        user=runtime_cred['MYSQL_GRANT_USER'],
        password=runtime_cred['MYSQL_GRANT_PASSWORD'],
        host=runtime_cred['MYSQL_GRANT_HOST'])
    try:
        user, passwd = random_credentials()
        with create_engine(conn_string).connect() as conn:
            conn.execute("CREATE USER %s@'%%' IDENTIFIED BY %s", (user, passwd))
            # TODO: validate grant db to prevent sql injections!
            conn.execute("GRANT {} ON {}.* TO '{}'@'%%'"
                .format(grant_list, runtime_cred['MYSQL_GRANT_DB'], user))
        return {'user': user, 'password': passwd}, None
    except Exception as e:
        return None, e

def create_sm_credentials(name, db_credentials):
    try:
        client = boto3.client('secretsmanager')
        resp = client.create_secret(
            Name=name,
            Description='Created by Runops Template',
            SecretString=json.dumps(db_credentials),
            Tags=[
                {
                    'Key': 'managed-by',
                    'Value': 'runops'
                },
            ]
        )
        return {'ARN': resp['ARN'],
                'VersionId': resp['VersionId']}, None
    except Exception as e:
        return None, e

class KubeConfigWriter(object):
    def __init__(self, kubeconfig_base64):
        """ Given a kubeconfig raw config in base64: kubectl config view --minify --raw -o json |jq -c |base64
        Decode it and write to a temporary file and return its path,
        on exit delete the temporary file
        """
        self.kubeconfig_base64 = kubeconfig_base64
        self.temp_kubeconfig_file = None
      
    def __enter__(self):
        raw_kubeconfig = base64.b64decode(self.kubeconfig_base64)
        self.temp_kubeconfig_file = tempfile.NamedTemporaryFile()
        self.temp_kubeconfig_file.write(raw_kubeconfig)
        self.temp_kubeconfig_file.seek(0)
        return self.temp_kubeconfig_file.name
  
    def __exit__(self, *args, **kwargs):
        self.temp_kubeconfig_file.close()

def dict_to_base64(data):
    return dict(map(lambda k : (k, base64.b64encode(data[k].encode('ascii')).decode()), data))

def create_k8s_secret(kubeconfig_base64, secret_name, namespace, db_credentials):
    try:
        with KubeConfigWriter(kubeconfig_base64) as kubeconfig_path:
            config.load_kube_config(config_file=kubeconfig_path)
            api_instance = client.CoreV1Api()
            sec = client.V1Secret()
            sec.metadata = client.V1ObjectMeta(
                name=secret_name,
                labels={'managed-by': 'runops'})
            sec.type = 'Opaque'
            sec.data = dict_to_base64(db_credentials)
            resp = api_instance.create_namespaced_secret(namespace=namespace, body=sec)
            return {'uid': resp.metadata.uid,
                    'resource_version': resp.metadata.resource_version,
                    'namespace': resp.metadata.namespace}, None
    except Exception as e:
        return None, e

if __name__ == '__main__':
    log.info('Parsing runtime credentials ...')
    runtime_cred, err = parse_runtime_credentials()
    if err: raise Exception(err)
    log.info('done.')

    log.info('Creating database user on MySQL with grants {} ...'.format(runtime_cred['MYSQL_GRANT_LIST']))
    db_credentials, err = create_db_user(runtime_cred, runtime_cred['MYSQL_GRANT_LIST'])
    if err:
        raise Exception('Failed to create credentials on database, err={}'.format(err))
    log.info('done. user={}'.format(db_credentials['user']))

    secret_suffix = secrets.token_hex(8)
    aws_secret_name = generate_secret_name(runtime_cred['AWS_SECRET_PREFIX'], secret_suffix)
    log.info('Creating database credentials on AWS Secret Manager. name={}, user={}'
        .format(aws_secret_name, db_credentials['user']))
    
    resp, err = create_sm_credentials(
        aws_secret_name,
        {**db_credentials, 
        'host': runtime_cred['MYSQL_GRANT_HOST'], 
        'database': runtime_cred['MYSQL_GRANT_DB']},
    )
    if err:
        raise Exception('Failed to create credentials on AWS Secret Manager, err={}'.format(err))
    log.info('done. arn={}, version_id={}'.format(resp['ARN'], resp['VersionId']))

    k8s_secret_name = generate_secret_name(runtime_cred['KUBERNETES_SECRET_PREFIX'], secret_suffix)
    log.info("Creating credentials on Kubernetes Secret with name={} ...".format(k8s_secret_name))
    resp, err = create_k8s_secret(
        runtime_cred['KUBECONFIG_DATA'], 
        k8s_secret_name,
        runtime_cred['SECRET_NAMESPACE'],
        {**db_credentials, 
        'host': runtime_cred['MYSQL_GRANT_HOST'], 
        'database': runtime_cred['MYSQL_GRANT_DB']},
    )
    if err:
        raise Exception('Failed to create credentials on Kubernetes Secret, err={}'.format(err))
    log.info('done. name={}, uid={}, resource_version={}, namespace={}'
        .format(
            k8s_secret_name, resp['uid'],
            resp['resource_version'], resp['namespace'],
        ))
