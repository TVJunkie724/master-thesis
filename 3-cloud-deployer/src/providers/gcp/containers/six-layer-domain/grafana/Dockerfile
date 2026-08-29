# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

FROM docker.io/grafana/grafana:12.4.2@sha256:83749231c3835e390a3144e5e940203e42b9589761f20ef3169c716e734ad505

ARG TARGETARCH

USER root
ADD --checksum=sha256:39d1cac9bcd2f7f2e46607319cb27afb8592ab0fcbc57968dc9fb86f3ef69a59 \
    https://grafana.com/api/plugins/yesoreyeram-infinity-datasource/versions/3.10.1/download?os=linux&arch=amd64 \
    /tmp/infinity.zip

RUN test "${TARGETARCH}" = "amd64" \
 && unzip -q /tmp/infinity.zip -d /var/lib/grafana/plugins \
 && test -f /var/lib/grafana/plugins/yesoreyeram-infinity-datasource/MANIFEST.txt \
 && test -x /var/lib/grafana/plugins/yesoreyeram-infinity-datasource/gpx_infinity_linux_amd64 \
 && chown -R 472:0 /var/lib/grafana/plugins/yesoreyeram-infinity-datasource \
 && chmod -R g=u /var/lib/grafana/plugins/yesoreyeram-infinity-datasource \
 && rm /tmp/infinity.zip

COPY --chown=472:0 grafana/provisioning /etc/grafana/provisioning
COPY --chown=472:0 grafana/dashboard.json.template /opt/twin2multicloud/dashboard.json.template
COPY --chown=472:0 --chmod=0555 grafana/entrypoint.sh /usr/local/bin/twin2multicloud-grafana

RUN mkdir -p /etc/grafana/provisioning/dashboards/content \
 && chown -R 472:0 /etc/grafana/provisioning /opt/twin2multicloud \
 && chmod -R g=u /etc/grafana/provisioning /opt/twin2multicloud

USER 472
ENTRYPOINT ["/usr/local/bin/twin2multicloud-grafana"]
