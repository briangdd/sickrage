FROM python:2.7.15-alpine3.8

ENV ACTIVATION_CODE Code
ENV LOCATION smart
ARG APP=expressvpn_2.0.0-1_amd64
MAINTAINER echel0n <echel0n@sickrage.ca>

ENV TZ 'Canada/Pacific'

# install app
COPY . /opt/sickrage/

RUN apk add --update --no-cache libffi-dev openssl-dev libxml2-dev libxslt-dev linux-headers build-base git tzdata unrar
RUN apt-get update && apt-get install -y transmission-daemon
RUN pip install -U pip setuptools
RUN pip install -r /opt/sickrage/requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates wget expect iproute2 \
    && rm -rf /var/lib/apt/lists/* \
    && wget -q "https://download.expressvpn.xyz/clients/linux/${APP}" -O /tmp/${APP} \
    && dpkg -i /tmp/${APP} 
    
COPY entrypoint.sh /tmp/entrypoint.sh
COPY expressvpnActivate.sh /tmp/expressvpnActivate.sh

# ports and volumes
EXPOSE 8081
VOLUME /config /downloads /tv /anime

ENTRYPOINT python /opt/sickrage/SiCKRAGE.py --nolaunch --datadir /config
