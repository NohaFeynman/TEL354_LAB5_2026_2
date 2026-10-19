# Imagen de ONOS para TEL354 - Laboratorio 5 (2026-2)
# Parte de la imagen oficial y solo agrega configuración: no añade capas
# pesadas, por lo que en un controller que ya tiene onosproject/onos:2.7.0
# la descarga es de pocos KB.
FROM onosproject/onos:2.7.0

LABEL org.opencontainers.image.title="tel354-onos" \
      org.opencontainers.image.description="ONOS 2.7.0 preconfigurado para TEL354 Lab 5" \
      org.opencontainers.image.source="https://github.com/NohaFeynman/TEL354_LAB5_2026_2"

# Apps que se activan al arrancar. openflow activa además openflow-base,
# lldpprovider, hostprovider y optical-model como dependencias.
# proxyarp responde los ARP con la información del HostService: sin ella,
# los ARP broadcast no coinciden con las reglas de los intents.
ENV ONOS_APPS=gui2,drivers,openflow,proxyarp

# El controller del slice tiene 1.9 GiB de RAM y no tiene swap.
ENV JAVA_OPTS="-Xms512m -Xmx1g"

# 8181: REST y GUI · 8101: CLI (SSH de Karaf) · 6653: OpenFlow
EXPOSE 8181 8101 6653

# El contenedor está "healthy" cuando ONOS acepta conexiones OpenFlow,
# es decir, cuando la app openflow ya está activa.
HEALTHCHECK --interval=10s --timeout=3s --start-period=90s --retries=3 \
  CMD bash -c 'exec 3<>/dev/tcp/127.0.0.1/6653' || exit 1
