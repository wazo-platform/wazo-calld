FROM python:2.7.9

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get -qq update \
    && apt-get -qq -y install \
       libpq-dev \
       libyaml-dev \
    && apt-get -yqq autoremove


WORKDIR /usr/src/
ADD . /usr/src/xivo-ctid-ng
RUN mkdir -p /usr/share/xivo-certs
ADD ./contribs/docker/certs /usr/share/xivo-certs
WORKDIR /usr/src/xivo-ctid-ng

RUN pip install -r requirements.txt
RUN python setup.py install
RUN cp -av etc/xivo-ctid-ng /etc
RUN mkdir -p /etc/xivo-ctid-ng/conf.d
RUN touch /var/log/xivo-ctid-ng.log
RUN chown www-data /var/log/xivo-ctid-ng.log
RUN mkdir -p /var/run/xivo-ctid-ng/
RUN chown www-data /var/run/xivo-ctid-ng/

RUN apt-get clean
RUN rm -fr /usr/src/xivo-ctid-ng
RUN rm -fr /var/lib/apt/lists/*

EXPOSE 9500

CMD ["xivo-ctid-ng", "-fd"]
