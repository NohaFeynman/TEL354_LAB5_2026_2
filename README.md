# TEL354 · Laboratorio 5 (2026-2): Intent-Based Networking con ONOS y Ansible

Material de la experiencia de laboratorio del curso **TEL354 - Redes Definidas
por Software** (PUCP). Se compara la misma intención de conectividad realizada
de dos formas:

| Enfoque | Herramienta | Quién calcula el camino | Quién mantiene las reglas |
|---|---|---|---|
| Imperativo | `ansible/ovs_direct.yml`: reglas OpenFlow por SSH en cada OVS, sin controlador | El operador (`host_vars/`) | Nadie: solo se corrigen al volver a ejecutar el playbook |
| Declarativo | `ansible/onos_intents.yml`: HostToHostIntents en ONOS | ONOS | ONOS (Intent Framework) |

Ambos playbooks leen la misma intención en `ansible/group_vars/all.yml`:

```yaml
connectivity:
  - [h1, h3]
```

## Estructura

```
docker/Dockerfile               imagen ONOS 2.7.0 preconfigurada
.github/workflows/onos-image.yml  construye y publica la imagen en GHCR
ansible/
  ansible.cfg, inventory.ini    switches sw1..sw3 por la red OOB (192.168.0.0/24)
  group_vars/all.yml            intención, hosts, controlador y API de ONOS
  host_vars/swX.yml             interfaz de cada switch hacia sus vecinos
  templates/flows.j2            traducción intención -> reglas OpenFlow
  ovs_reset.yml                 switches sin controlador ni reglas (secure, OF1.3)
  ovs_direct.yml                enfoque imperativo (admite --check --diff)
  ovs_connect.yml               conecta los switches a ONOS
  onos_intents.yml              enfoque declarativo (crea y elimina intents)
```

## Imagen de ONOS

`ghcr.io/nohafeynman/tel354-onos:2026-2` parte de `onosproject/onos:2.7.0` y
solo agrega configuración:

- `ONOS_APPS=gui2,drivers,openflow,proxyarp` (openflow activa además
  openflow-base, lldpprovider, hostprovider y optical-model).
- `JAVA_OPTS="-Xms512m -Xmx1g"`: el controller del slice tiene 1.9 GiB de RAM y no tiene swap.
- `HEALTHCHECK` sobre el puerto OpenFlow 6653.

Como no agrega capas de archivos, en un controller que ya descargó
`onosproject/onos:2.7.0` la descarga es casi nula.

```bash
sudo docker run -d --name onos --network host --restart unless-stopped \
  ghcr.io/nohafeynman/tel354-onos:2026-2
sudo docker ps            # STATUS debe llegar a (healthy)
ssh-keygen -R "[localhost]:8101"
ssh -p 8101 -o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-rsa \
  -o PubkeyAcceptedAlgorithms=+ssh-rsa onos@localhost      # contraseña: rocks
```

La imagen se publica sola al hacer push de cambios en `docker/` a `main`
(o manualmente desde *Actions > Imagen ONOS (GHCR) > Run workflow*). Tras la
primera publicación, el paquete debe hacerse público en
*GitHub > Packages > tel354-onos > Package settings > Change visibility*.

## Ansible en el controller

```bash
sudo apt install -y --no-install-recommends ansible-core git
git clone https://github.com/NohaFeynman/TEL354_LAB5_2026_2.git
cd TEL354_LAB5_2026_2/ansible

# Acceso por clave a los switches (contraseña de ubuntu en cada uno)
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
for i in 11 12 13; do ssh-copy-id -o StrictHostKeyChecking=accept-new ubuntu@192.168.0.$i; done
ansible switches -m ping
# Cada ansible-playbook pide "BECOME password:" (contraseña de sudo de los switches)

ansible-playbook ovs_reset.yml
ansible-playbook ovs_direct.yml                 # enfoque imperativo
ansible-playbook ovs_direct.yml --check --diff  # detectar deriva sin corregir
ansible-playbook ovs_connect.yml                # conectar a ONOS
ansible-playbook onos_intents.yml               # enfoque declarativo
```

## Historial

La versión 2026-1 (aplicación RBAC en Python y la app `packet-bridge` en
formato `.oar`) se retiró: la experiencia 2026-2 se centra en la comparación
entre automatización imperativa e intents.
