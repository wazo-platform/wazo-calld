FROM python:3.5-stretch

ENV DEBIAN_FRONTEND noninteractive

ADD . /usr/src/wazo-calld
ADD ./contribs/docker/certs /usr/share/xivo-certs

WORKDIR /usr/src/wazo-calld

RUN true \
    && apt-get -qq update \
    && apt-get -qq -y install libpq-dev libyaml-dev ghostscript \
    && pip install -r requirements.txt \
    && python setup.py install \
    && cp -av etc/wazo-calld /etc \
    && install -m 755 -o root -g www-data bin/wazo-pdf2fax /usr/bin/wazo-pdf2fax \
    && mkdir -p /etc/wazo-calld/conf.d \
    && touch /var/log/wazo-calld.log \
    && chown www-data /var/log/wazo-calld.log \
    && install -d -o www-data -g www-data /var/run/wazo-calld/ \
    && apt-get clean \
    && rm -fr /usr/src/wazo-calld /var/lib/apt/lists/* \
    && true

EXPOSE 9500

CMD ["wazo-calld", "-fd"]
