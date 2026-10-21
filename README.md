# TEL354 · Laboratorio 5 (2026-2): programación de redes SDN con ONOS

Material del laboratorio 5 del curso **TEL354 - Redes Definidas por Software**
(PUCP). ONOS es el protagonista: el informe previo trabaja el enfoque
proactivo con su API REST (intents) y la experiencia, el enfoque reactivo
(PACKET_IN, PACKET_OUT y FLOW_MOD).

Ansible se usa solo para el **bootstrap** de la red: dejar el slice en un
estado inicial conocido. No instala flows: las reglas de tráfico las programa
ONOS en las tablas de los switches (el datapath, que en un switch físico es el
ASIC), y no un script que configure cada equipo por SSH.

## Estructura

```
docker/Dockerfile                 imagen ONOS 2.7.0 preconfigurada para la experiencia
.github/workflows/onos-image.yml  construye y publica la imagen en GHCR
ansible/
  ansible.cfg, inventory.ini      switches sw1..sw3 por la red OOB (192.168.0.0/24)
  group_vars/all.yml              dirección del controlador y de la API de ONOS
  bootstrap.yml                   espera a ONOS y conecta los switches (secure, OF1.3, sin reglas)
  ovs_reset.yml                   switches sin controlador ni reglas
  slice_reset.yml                 borra el contenedor y tshark del controller y ejecuta ovs_reset
rbac/
  packet-bridge-1.0.0.oar         app ONOS (Java): reenvía cada PACKET_IN IPv4 por HTTP al puerto 5000
  rbac_app.py                     decide con policy.yaml: HostToHostIntent (permitido) o regla DROP (denegado)
  policy.yaml                     roles de h1..h4 y reglas entre roles
```

## Ansible en el controller

```bash
sudo apt install -y --no-install-recommends ansible-core git
git clone https://github.com/NohaFeynman/TEL354_LAB5_2026_2.git
cd TEL354_LAB5_2026_2/ansible

ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
for i in 11 12 13; do ssh-copy-id -o StrictHostKeyChecking=accept-new ubuntu@192.168.0.$i; done
ansible switches -m ping

ansible-playbook bootstrap.yml     # con ONOS ya levantado
ansible-playbook slice_reset.yml   # al terminar
```

Cada `ansible-playbook` pide `BECOME password:` (contraseña de sudo: `ubuntu`).

## Imagen de ONOS

`ghcr.io/nohafeynman/tel354-onos:2026-2` parte de `onosproject/onos:2.7.0` y
solo agrega configuración (`ONOS_APPS`, `JAVA_OPTS` y un `HEALTHCHECK` sobre el
puerto 6653), por lo que en un controller que ya tiene la imagen oficial la
descarga es casi nula.

```bash
sudo docker run -d --name onos --network host --restart unless-stopped \
  ghcr.io/nohafeynman/tel354-onos:2026-2
```

La imagen se publica sola al hacer push de cambios en `docker/` a `main`.

## Control de acceso reactivo (RBAC)

```bash
cd ~/TEL354_LAB5_2026_2/rbac
curl -s -u onos:rocks -X POST -H 'Content-Type: application/octet-stream' \
  --data-binary @packet-bridge-1.0.0.oar \
  'http://localhost:8181/onos/v1/applications?activate=true'
python3 rbac_app.py        # solo biblioteca estándar + PyYAML (incluido en Ubuntu)
```

`packet-bridge` es la app del ciclo 2026-1. Su `.oar` original tenía
`features=""` en `app.xml`, por lo que ONOS activaba la app sin cargar el
bundle; el `.oar` de este repositorio incluye el descriptor de features y
conserva el mismo `.jar`. La app en Python es una versión simplificada de la
de 2026-1: solo modo reactivo, sin MAC fijas (las toma del PACKET_IN) y sin
dependencias externas.
