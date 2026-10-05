# TODO — ALPI

Só o que falta. Arquitetura e justificativas em `PROPOSTA.md`.

## 0. Decisões em aberto

- [ ] Criar um `packages_absent` (desinstalação explícita) ou o alpi só instala?
- [ ] Id desconhecido no catálogo: derrubar a execução (recomendado) ou só avisar?
- [ ] O perfil pode trazer conjuntos de pacotes, ou só política?
- [ ] VirtualBox no Fedora: fonte fixa por distro ou o usuário escolhe o repositório da Oracle?
- [ ] Existe VM ou testador de Debian/Ubuntu antes desses ports?
- [ ] Primeira leva de desktops: GNOME, KDE ou os dois?

## 1. Esqueleto

- [ ] `bootstrap.sh` com detecção via `/etc/os-release` (dnf/apt) e collections fixadas por versão.
- [ ] `site.yml` + `tasks/env_setup.yml`: matriz de suporte (assert) → detecção → `group_by`.
- [ ] `group_vars/os_*` e `group_vars/profile_*` com `ansible_group_priority`.
- [ ] `catalog.yml` + resolução de pacotes (`set_fact` único) + validação de ids.
- [ ] `host_vars/127.0.0.1/{bootstrap,custom}.yml` + `custom.yml.example`.

## 2. Trazer o AFPI (Fedora, perfil `personal`)

- [ ] Portar as roles com as tasks específicas em `tasks/Fedora.yml`.
- [ ] Role `repos` nova (RPM Fusion, COPR) rodando primeiro.
- [ ] Aliases pessoais (`open/close-thevoid`, UUID LUKS) para `host_vars`.
- [ ] Gates por feature: VirtualBox (hoje busca de string), ClamAV (freshclam sem condição), overrides de Flatpak só para apps instalados.
- [ ] `flatpak_filesystem_overrides` vazio no repo, ZapZap no `custom.yml.example`.

## 3. Trazer o AAPI (AlmaLinux 10, perfil `work`)

- [ ] `group_vars/os_AlmaLinux_10` + `tasks/RedHat.yml` (dnf4, CRB/EPEL, Oracle VirtualBox).
- [ ] Limpeza dos dois blocos legados do `.zshrc`.

## 4. Paridade

- [ ] Teste de referência: conjuntos resolvidos por (distro, perfil, DE) comparados com o AFPI e o AAPI.
- [ ] Containers `fedora:44` e `almalinux:10`, duas vezes (idempotência).
- [ ] VM com EFI + Secure Boot.
- [ ] Congelar o AAPI e o AFPI com README apontando para o ALPI.

## 5. Novas distros (só com VM de teste)

- [ ] Debian 13.
- [ ] Ubuntu 26.04 LTS.
