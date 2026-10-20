# Moving files between the host and the VMs (text mode)

For a VM with only a console, no clipboard and no shared folder: for example, to get
`run0.log`/`run1.log` out of a [checklist](vm-checklist.md) run or to send a file in.

## Why `10.0.2.2` does not work

In VirtualBox NAT, `10.0.2.2` is the host as seen from the VM, but:

- Since VirtualBox 7, NAT blocks access to the host's loopback by default
  (`localhostReachable="0"` in `VBoxManage showvminfo <vm> --machinereadable`). A server on the
  host listening on `127.0.0.1` cannot be reached from the VM.
- Listening on `0.0.0.0` is not enough on its own: the host's firewalld blocks the port, and
  opening it needs sudo.

The way around both is the other direction: **the server runs in the VM and the host connects
to it** through a NAT port forward. The rule can be added while the VM is running, without
disturbing a run in progress.

In the commands below, replace `fedora44-alpi` with the VM's name (`VBoxManage list runningvms`)
and `user` with the user inside it.

## Option 1: SSH/scp (both directions)

On the host:

```bash
VBoxManage controlvm fedora44-alpi natpf1 "ssh,tcp,127.0.0.1,2222,,22"
```

In the VM:

```bash
sudo systemctl enable --now sshd
```

On the host:

```bash
scp -P 2222 user@127.0.0.1:~/run1.log .    # VM to host
scp -P 2222 file user@127.0.0.1:~          # host to VM
```

## Option 2: no sshd, VM to host only

On the host:

```bash
VBoxManage controlvm fedora44-alpi natpf1 "http,tcp,127.0.0.1,8080,,8000"
```

In the VM, in the files' directory:

```bash
python3 -m http.server 8000
```

On the host:

```bash
curl -O http://127.0.0.1:8080/run1.log
```

## Removing the rules

```bash
VBoxManage controlvm fedora44-alpi natpf1 delete ssh    # or: delete http
```

With more than one VM at a time, give each one its own host port (for example `2222` and
`2223`).
