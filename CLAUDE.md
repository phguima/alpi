# ALPI — instruções para o Claude

ALPI (Ansible Linux Post-Install): unifica o AFPI (`phguima/afpi`, Fedora, máquina pessoal `noir`)
e o AAPI (`phguima/aapi`, AlmaLinux 10, máquina do trabalho) num só projeto que detecta a distro.
Repo público `phguima/alpi`, branch única `main`, GPL-3.0. O usuário conversa em português.

## Estado do trabalho

Em fase de desenho (criado em 2026-10-05). `PROPOSTA.md` tem a arquitetura (revisada por um
agente adversarial); `TODO.md` tem **só o que falta**, começando pelas decisões em aberto. **Ler
os dois antes de começar.** Ao concluir um item, removê-lo do `TODO.md` e registrar a validação
na mensagem do commit.

Decisão de 2026-10-05: repo **novo**, sem o histórico do AFPI. O AFPI e o AAPI continuam ativos
até a paridade; o código entra aos poucos, portado deles. Mudanças feitas lá no meio-tempo
(ex.: `flatpak_filesystem_overrides`) precisam ser trazidas para cá.

## Git

- Começar com `git fetch` + `git pull --ff-only`: o usuário também commita de outras máquinas.
- Commit e push **só quando o usuário pedir**. Commits em inglês, Conventional Commits com escopo
  (`feat(apps): …`, `docs(todo): …`).

## Testes — em container ou VM, nunca no host

Nada roda no host (a máquina pessoal do usuário), nem leitura, nem `--check`. Validar em podman
(`registry.fedoraproject.org/fedora:44`, `docker.io/library/almalinux:10`, …), **duas vezes**
(`changed=0` na 2ª). No Fedora com SELinux, montar o repo com `--security-opt label=disable`
(sem `:z`, para não reetiquetar os arquivos). As receitas de simulação (Secure Boot falso,
`mokutil` falso, sessão GNOME via D-Bus) estão no `CLAUDE.md` do AFPI e do AAPI. Hardware
(Secure Boot/MOK, reboot) vai para a VM do usuário; resultados chegam como screenshots em
`~/Pictures/Screenshots` (listar o diretório e pegar os mais novos).
