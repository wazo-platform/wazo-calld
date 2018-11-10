FROM python:3.5-stretch

ENV DEBIAN_FRONTEND noninteractive

ADD . /usr/src/xivo-ctid-ng
ADD ./contribs/docker/certs /usr/share/xivo-certs

WORKDIR /usr/src/xivo-ctid-ng

RUN true \
    && apt-get -qq update \
    && apt-get -qq -y install libpq-dev libyaml-dev \
    && pip install -r requirements.txt \
    && python setup.py install \
    && cp -av etc/xivo-ctid-ng /etc \
    && mkdir -p /etc/xivo-ctid-ng/conf.d \
    && touch /var/log/xivo-ctid-ng.log \
    && chown www-data /var/log/xivo-ctid-ng.log \
    && install -d -o www-data -g www-data /var/run/xivo-ctid-ng/ \
    && apt-get clean \
    && rm -fr /usr/src/xivo-ctid-ng /var/lib/apt/lists/* \
    && true

EXPOSE 9500

CMD ["xivo-ctid-ng", "-fd"]
