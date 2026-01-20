# rov2


# Shared One Time RPI Setup commands
I ran these commands

```bash
sudo apt update
sudo apt install ssh
sudo /etc/init.d/ssh start
sudo passwd rov    # for surface
sudo passwd pi     # for rov
```

```bash
# ssh into the pi
nano .ssh/authorized_keys
# paste in contents of id_ed25519.pub
chmod 600 authorized_keys
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


# rov
```bash
cd rov
python3 rov_receiver.py
```

# surface
If running from vs code:

```
cd surface
DISPLAY=:0 python3 ./rov_dashboard.py
```

stop from another terminal
```
sudo pkill -f rov_dashboard.py
```

# if the ip changes
If the ips change, you need to tell windows

```bash
cd ~
cd .ssh
code config
```

# setup static network
```bash
nmcli connection show


sudo nmcli connection modify "Wired connection 1" ipv4.addresses 192.168.2.204/24
sudo nmcli connection modify "Wired connection 1" ipv4.method manual\
# next two are maybe not required?
sudo nmcli connection modify "Wired connection 1" ipv4.never-default yes
sudo nmcli connection modify "Wired connection 1" ipv4.route-metric 1000
sudo nmcli connection up "Wired connection 1"



sudo nmcli connection modify "Wired connection 1" ipv4.addresses 192.168.2.13/24
sudo nmcli connection modify "Wired connection 1" ipv4.method manual
sudo nmcli connection up "Wired connection 1"



```