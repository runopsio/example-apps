# PHP + Laravel + Tinker

This examples demonstrate how to setup a runops agent in a standalone VM allowing to run commands inside a laravel project using [Artisan Tinker REPL](https://laravel.com/docs/8.x/artisan#tinker)

## Apps

- [PHP 8.1](https://www.php.net/releases/8.1/en.php)
- [Laravel 8](https://laravel.com/docs/8.x/starter-kits)
- [Tinker (PsySH)](https://github.com/bobthecow/psysh)

## Requirements

- [Vagrant Box](https://www.vagrantup.com/)

## Setup

1. Open an terminal and execute the steps below

```sh
git clone https://github.com/runopsio/example-apps.git && cd example-apps/laravel
vagrant up
vagrant ssh
sudo su -
# /opt/start-agent.sh <agent-token> <tag> </path/to/laravel/project/artisan>
/opt/start-agent.sh mytoken dev /opt/example-app/artisan
```

> It's possible to map several laravel projects in the same agent.

2. Open another terminal, create a target and execute a command in REPL

```sh
runops targets create --name example-app-repl --type bash --secret_provider env-var --secret_path APP_CONFIG --tags local
runops tasks create -t example-app-repl -s 'array_slice(getenv(), 0, 5)'
=> [
     "PWD" => "/root",
     "HOME" => "/home/runops",
     "SHLVL" => "0",
     "PHP_APP" => "/opt/example-app/artisan",
     "PATH" => "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin",
   ]
```

> This example uses a feature called **Custom Commands** on targets which aren't general available yet, after creating a target,
> a **runops member** needs to configure manually the command which will be executed in the agent, in this example is `php [[PHP_APP]] tinker -n`

3. [Optional] Use the runops REPL instead

```sh
runops tasks repl
REPL started, each command will be executed remotely
and displayed in this session. https://runops.io/docs/user-guides/REPL
Type :help to list available commands

=> :target example-app-repl
example-app-repl=>
#_=> function helloWorldMsg() {
#_=>   print "Hello World from Runops!\n";
#_=> }
#_=> helloWorldMsg();
#_=>
Hello World from Runops!
=> null
```
