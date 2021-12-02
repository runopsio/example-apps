if [ "$#" -ne 3 ]; then
  echo "expected 3 args, try: $0 <TOKEN> <TAG> <LARAVEL-APP>"
  exit 1
fi

export TOKEN=$1
export TAGS=$2
export APP_CONFIG="{\"PHP_APP\": \"$3\"}"
export JWK_URL=https://runops.us.auth0.com/.well-known/jwks.json
java -jar /opt/agent-standalone.jar
