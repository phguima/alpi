# ALPI — Ansible Linux Post-Install

Proposta de arquitetura (2026-10-05). Revisada após crítica adversarial.

## Objetivo

Um único projeto que detecta a distro em execução e aplica o pós-instalação correto. Hoje ele seria a união do **AFPI** (Fedora, máquina pessoal `noir`) com o **AAPI** (AlmaLinux 10, máquina de trabalho). Depois, ele deve receber outras distros (Debian, Ubuntu…).

## Ponto de partida

O afpi e o aapi têm a mesma estrutura e compartilham 6 roles (`update`, `hardware`, `common`, `apps`, `desktop`, `ai_tools`). O afpi tem duas roles a mais: `nvidia` e `akmods_mok`. Os dois já começam a se distanciar. Por exemplo, o aapi não recebeu a correção de dono dos ícones (`af80a16`) nem vários `check_mode: false`.

| Diferença | Exemplo | Natureza |
|---|---|---|
| Nome de pacote | `vim` → `vim-enhanced`, `shellcheck` → `ShellCheck`, `p7zip` → `7zip` | dado por distro |
| Pacote ausente na distro | Telegram/Drawy via Flatpak no EL10, Roboto do upstream, argyllcms/chkrootkit/unhide | dado por distro |
| Repositórios | RPM Fusion + COPR (Fedora); CRB + EPEL + RPM Fusion EL + Oracle (Alma) | tasks por família |
| Comportamento | dnf5 × dnf4 (`repo list --json` × `repolist`), VirtualBox akmod + kmodgenca × Oracle + chave própria, `@grupos`, `.i686`, `allowerasing` | tasks por distro |
| Ferramental | `ansible` × `ansible-core`, `community.general <12` no EL10 (ansible-core 2.16) | bootstrap |
| Hardware | NVIDIA, ASUS, AMD freeworld | detectado |
| Máquina/usuário | hostname, aliases `open/close-thevoid` com UUID LUKS do noir | por máquina |

## Abordagem escolhida: unificação (B)

A alternativa descartada (A) seria um dispatcher fino que chama o afpi ou o aapi como submódulos. Ela mantém a duplicação, e cada distro nova viraria um repositório inteiro.

### Três eixos independentes

1. **Distro**: detectada a partir de `ansible_facts`.
2. **Hardware**: detectado (NVIDIA, ASUS, AMD, Secure Boot). O perfil ou o usuário pode **apenas vetar** (`nvidia: auto | false`).
3. **Máquina/usuário**: fica em `host_vars`, fora do git. O UUID do thevoid sai do repositório e vem para cá.

O **perfil** (`personal`, `work`) fica pequeno: política de hostname, Steam e extras pessoais.

### Estrutura

```
alpi/
  bootstrap.sh              # lê /etc/os-release → instala ansible via dnf/apt; pina collections por versão
  site.yml
  catalog.yml               # ids lógicos de pacote → nome por distro (ver "Personalização")
  tasks/env_setup.yml       # matriz de suporte (assert) → detecção → group_by → resolução de pacotes
  group_vars/
    all/                    # comum: usuário, git, flatpaks, zsh, ai_tools; secrets.yml (vault)
    os_Fedora/  os_AlmaLinux_10/  os_Debian_13/ …
    profile_personal/  profile_work/
  host_vars/127.0.0.1/      # git-ignored
    bootstrap.yml           # escrito pelo bootstrap (hostname, identidade git)
    custom.yml              # escrito pelo usuário (ver custom.yml.example)
  roles/
    repos/                  # NOVA, roda primeiro: rpmfusion/epel/crb/copr | apt sources/extrepo/PPA
    update/ common/ apps/ desktop/ hardware/ nvidia/ ai_tools/
    mok/                    # assinadores separados: kmodgenca (/etc/pki/akmods), vboxdrv Oracle
                            # (/var/lib/shim-signed/mok), DKMS (/var/lib/dkms/mok.*). Mantém os
                            # caminhos atuais para não exigir re-enroll em máquinas existentes.
```

Dentro de cada role, as tasks específicas ficam em `tasks/{Fedora,RedHat,Debian}.yml`. `ansible.builtin.package` é usado só para as listas de pacotes simples. dnf e apt continuam explícitos onde o comportamento difere.

### Regras de projeto

- **Precedência:** não usar `include_vars` para distro/perfil, porque ele tem prioridade maior que `host_vars` e o perfil passaria por cima do usuário sem aviso. Em vez disso, `group_by` cria grupos dinâmicos (`os_<distro>_<major>`, `profile_<nome>`) e os dados ficam em `group_vars/`, ordenados com `ansible_group_priority`. Assim `host_vars` e `-e` continuam por cima.
- **Suporte explícito:** uma allowlist de (distro, versão) com assert antes de carregar qualquer variável. Nada de fallback silencioso por `os_family`: Fedora, Rocky e CentOS Stream têm `os_family = RedHat`, e Ubuntu cai em `Debian`.
- **Facts:** `inject_facts_as_vars = False` continua valendo, então sempre `ansible_facts[...]`.
- **Ansible:** usar o ansible-core da própria distro, com o código escrito para a versão mínima suportada (hoje 2.16, a do EL10). Reavaliar um venv com versão fixa se alguma distro trouxer uma versão menor.

## Personalização de pacotes

### Dois níveis

- **Features**: itens que têm tasks de configuração (virtualbox, steam, vscode, brave, gh, antigravity, clamav, nvidia, asus…). Liga e desliga por flag. **Nunca** se desliga uma feature apagando o nome de um pacote.
- **Packages**: itens simples, sem configuração, resolvidos pelo catálogo.

### Catálogo (no repositório)

```yaml
# catalog.yml: id lógico -> pacote em cada distro
vim:      {Fedora: vim, RedHat: vim-enhanced, Debian: vim}
7zip:     {Fedora: [p7zip, p7zip-plugins], RedHat: [7zip, 7zip-standalone]}
telegram: {Fedora: telegram-desktop, RedHat: {flatpak: org.telegram.desktop}}
steam:    {Fedora: steam, RedHat: ~}     # ~ = indisponível: pula e avisa
aliases:  {p7zip: 7zip}                  # ids renomeados continuam resolvendo
```

### Arquivo do usuário (fora do git)

```yaml
# host_vars/127.0.0.1/custom.yml
features:      {virtualbox: false, clamav: false}
packages_add:  [vim, "rpm:sqlitebrowser", "flatpak:org.gimp.GIMP"]   # prefixo = nome cru, sem catálogo
packages_skip: [discord]
```

### Regras

- **Combinação:** cada camada usa chaves próprias (`packages_base`, `packages_profile`, `packages_add`, `packages_skip`). Um único `set_fact` monta a lista final: `(base + perfil + add) | unique | difference(skip)`. O usuário é aplicado por último. Nunca usar `hash_behaviour`.
- **Validação** (em `env_setup`):
  - um id desconhecido derruba a execução logo no início e lista todos os erros;
  - um id `~` na distro atual é pulado com aviso (ou falha, com `strict: true`);
  - nomes crus com prefixo são conferidos com `dnf repoquery` / `apt-cache policy`.
- **Isolamento:** os extras do usuário são instalados numa task separada, depois da base, para que um erro de digitação não derrube a instalação inteira.
- **Remoção:** `skip` significa "não instalar", **nunca** "desinstalar". Tirar um pacote dos defaults também não desinstala. Não há registro do que o alpi instalou.
- **Arquivos separados:** o bootstrap regrava o `bootstrap.yml` dele com PyYAML, o que apagaria comentários escritos à mão. Por isso o `custom.yml` fica em arquivo separado. Como os dois ficam fora do git, o `git pull` nunca conflita.
- **Sem seletor interativo no bootstrap:** seria reimplementar o catálogo em bash.

### Permissões de Flatpak (já existe no afpi/aapi)

Em 2026-10-05 o afpi e o aapi ganharam `flatpak_filesystem_overrides` (`group_vars/all/all.yml`) e a task `Software | Grant extra folders to flatpak applications` (`roles/apps`). É um mapa app → pastas, aplicado com `flatpak override --user --filesystem=…`:

```yaml
flatpak_filesystem_overrides:
  com.rtosta.zapzap:
    - "{{ user_home }}/wks:ro"   # arrastar arquivos de ~/wks para o ZapZap
```

O motivo: o sandbox do Flatpak só enxerga as pastas liberadas. Um arquivo arrastado de outro lugar chega ao app como um caminho que ele não consegue abrir (o ZapZap diz que o arquivo "não tem conteúdo"). O seletor de arquivos passa pelo portal e não precisa de permissão.

No alpi:
- As pastas são do usuário (`~/wks` é pessoal), então o mapa vai para o `custom.yml`. O repositório traz o mapa vazio, com o ZapZap no `custom.yml.example`.
- Os overrides fixos de Bitwarden e Zoom (Wayland, cedilha) podem virar o mesmo mecanismo, generalizado para `flatpak_overrides: {app: [flags]}` e aplicado só quando o app estiver no conjunto resolvido.

### Armadilhas no código atual a corrigir na migração

- O gate do VirtualBox é uma busca de string: `'VirtualBox' in dnf_packages_common` (`afpi/roles/apps/tasks/main.yml:25`).
- O `clamav-freshclam` é habilitado sem condição: se o ClamAV for pulado, a execução quebra.
- Os overrides de Flatpak do Bitwarden e do Zoom rodam mesmo quando esses apps não estão instalados.

Cada um desses vira uma feature ou passa a ser protegido pelo conjunto de pacotes resolvido.

## Testes

- **Teste de referência:** um play que só imprime os conjuntos de pacotes, flatpaks e features resolvidos para cada (distro, perfil, DE). A saída é comparada com o que o afpi e o aapi instalam hoje. É ele que prova a paridade.
- **Containers podman** (`fedora:44`, `almalinux:10`, …) por role, rodando duas vezes para checar idempotência. O `site.yml` completo não roda em container (sem systemd/grub).
- **VM** para Secure Boot/MOK e para o desktop completo.
- Nunca rodar no host, nem com `--check`.

## Migração

1. **Repositório novo `phguima/alpi`** (decidido em 2026-10-05, em vez de renomear o afpi). O código é portado do afpi e do aapi aos poucos. Os caminhos `host_vars/127.0.0.1.yml` (migrado para o diretório) e `group_vars/all/secrets.yml` continuam compatíveis.
2. **Reestruturar** para os três eixos, o catálogo, a role `repos` e o `group_by`. Os aliases pessoais vão para `host_vars`.
3. **Incorporar os deltas do aapi** como `os_AlmaLinux_10` + perfil `work`. Levar junto as duas limpezas de bloco legado do `.zshrc` (`NVIDIA AND API CONFIGURATION` e `API CONFIGURATION`).
4. **Provar a paridade** com o teste de referência + containers + VM.
5. **Congelar o aapi** com um README apontando para o alpi. O trabalho em andamento no afpi (reinstalação do noir, passo 8) termina antes do rename, ou é portado.
6. **Debian 13 / Ubuntu 26.04 LTS**: só depois de existir VM de teste. Cada um é um port à parte: `/var/run/reboot-required`, `update-grub`, Flatpak ausente no Ubuntu, Firefox em snap, extrepo/PPA, DKMS.

## Decisões em aberto

1. ~~Renomear o afpi ou criar um repositório novo?~~ **Decidido (2026-10-05):** repositório novo e vazio, `phguima/alpi`, público, GPL-3.0. O afpi e o aapi seguem ativos até a paridade.
2. Criar um `packages_absent` para desinstalar de forma explícita, ou o alpi só instala?
3. Id desconhecido no catálogo: derrubar a execução (recomendado) ou só avisar?
4. O perfil pode trazer conjuntos de pacotes, ou só política?
5. VirtualBox no Fedora: a fonte é fixa por distro, ou o usuário pode escolher o repositório da Oracle?
6. Existe VM ou testador de Debian/Ubuntu antes de começarmos esses ports?
7. Primeira leva de desktops: GNOME, KDE ou os dois?
