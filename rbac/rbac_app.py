#!/usr/bin/env python3
"""Control de acceso por roles (RBAC) reactivo sobre ONOS.

Flujo:
  1. Un switch envía un PACKET_IN de IPv4 a ONOS.
  2. La app packet-bridge (Java, dentro de ONOS) lo reenvía por HTTP a
     POST http://127.0.0.1:5000/packet-in y descarta el paquete.
  3. Esta app consulta policy.yaml y decide:
       - permitido: crea un HostToHostIntent entre ambos hosts (ONOS instala
         las reglas en todos los switches del camino);
       - denegado: instala una regla DROP temporal en el switch de ingreso.

Solo usa la biblioteca estándar de Python y PyYAML (incluido en Ubuntu).
Uso:  python3 rbac_app.py            (Ctrl+C para detener)
"""
import base64
import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yaml

ONOS = os.getenv('ONOS_URL', 'http://127.0.0.1:8181') + '/onos/v1'
AUTH = 'Basic ' + base64.b64encode(b'onos:rocks').decode()
APP_ID = 'edu.pucp.sdn.packetbridge'      # registrado por packet-bridge
POLICY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'policy.yaml')
DROP_TIMEOUT = 30                          # segundos

policy = yaml.safe_load(open(POLICY))
hosts = {ip: h for ip, h in policy['hosts'].items()}
lock = threading.Lock()
decided = {}                               # (src_ip, dst_ip) -> decisión ya aplicada


def log(msg):
    print(f'{datetime.now():%H:%M:%S}  {msg}', flush=True)


def onos(method, path, body=None):
    req = urllib.request.Request(ONOS + path, method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={'Authorization': AUTH, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, r.headers.get('Location', '')


def decide(src_ip, dst_ip):
    """Devuelve (permitido, texto) según los roles de origen y destino."""
    src, dst = hosts.get(src_ip), hosts.get(dst_ip)
    if not src or not dst:
        return False, 'host desconocido'
    for rule in policy['rules']:
        if rule['src'] == src['role'] and rule['dst'] == dst['role']:
            return rule['allow'], f"{src['role']} -> {dst['role']}"
    return False, f"{src['role']} -> {dst['role']} (sin regla: denegado por defecto)"


def apply(p):
    src_ip, dst_ip = p['src_ip'], p['dst_ip']
    name = lambda ip: hosts.get(ip, {}).get('name', ip)
    log(f"[PACKET_IN] {p['device_id']} puerto {p['in_port']}  "
        f"{name(src_ip)} ({src_ip}) -> {name(dst_ip)} ({dst_ip})  proto={p['ip_proto']}")
    with lock:
        if (src_ip, dst_ip) in decided:
            log(f"            decisión ya aplicada: {decided[(src_ip, dst_ip)]}")
            return
        allow, why = decide(src_ip, dst_ip)
        decided[(src_ip, dst_ip)] = 'ALLOW' if allow else 'DENY'
    try:
        if allow:
            _, loc = onos('POST', '/intents', {
                'type': 'HostToHostIntent', 'appId': APP_ID,
                'one': f"{p['eth_src']}/None", 'two': f"{p['eth_dst']}/None"})
            with lock:
                decided[(dst_ip, src_ip)] = 'ALLOW'      # el intent es bidireccional
            log(f"[ALLOW]     {why}: HostToHostIntent key={loc.rsplit('/', 1)[-1]}")
        else:
            onos('POST', f"/flows/{p['device_id']}?appId={APP_ID}", {
                'priority': 40001, 'timeout': DROP_TIMEOUT, 'isPermanent': False,
                'deviceId': p['device_id'],
                'selector': {'criteria': [
                    {'type': 'ETH_TYPE', 'ethType': '0x0800'},
                    {'type': 'IPV4_SRC', 'ip': f'{src_ip}/32'},
                    {'type': 'IPV4_DST', 'ip': f'{dst_ip}/32'}]},
                'treatment': {'instructions': []}})
            log(f"[DENY]      {why}: regla DROP en {p['device_id']} por {DROP_TIMEOUT} s")
            threading.Timer(DROP_TIMEOUT, lambda: decided.pop((src_ip, dst_ip), None)).start()
    except urllib.error.HTTPError as e:
        log(f"[ERROR]     ONOS respondió HTTP {e.code}: {e.read().decode()[:200]}")
        with lock:
            decided.pop((src_ip, dst_ip), None)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/packet-in':
            self.send_response(404); self.end_headers(); return
        p = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        self.send_response(200); self.end_headers()          # responde rápido a ONOS
        threading.Thread(target=apply, args=(p,), daemon=True).start()

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    log(f'RBAC escuchando en http://127.0.0.1:5000/packet-in  (política: {POLICY})')
    for ip, h in hosts.items():
        log(f"            {h['name']:3} {ip:10} rol={h['role']}")
    ThreadingHTTPServer(('127.0.0.1', 5000), Handler).serve_forever()
