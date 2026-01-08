# rov2


# Shared One Time RPI Setup commands
I ran these commands

```bash
sudo apt update
sudo apt install ssh
sudo /etc/init.d/ssh start
sudo passwd rov
```


# Windows One Time setup
* install vscode
* install git (vscode will prompt you to do this)
* setup .ssh/config
  * right click in windows, run "Open git bash here"

```bash
cd
cd .ssh
nano config
```


# vscode setup
* install cpp extension `@id:ms-vscode.cpptools-extension-pack`
* install remote tunnels `ms-vscode.remote-server` and remote ssh


# vscode shortcuts
* `ctrl+~`  open terminal
* `ctrl+shift+~` open new terminal
