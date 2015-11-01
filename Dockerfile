FROM python:2.7

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get -qq update \
    && apt-get -qq -y install \
       libpq-dev \
       libyaml-dev \
       vim \
    && apt-get -yqq autoremove


WORKDIR /usr/src/
ADD . /usr/src/xivo-ctid-ng
RUN mkdir /usr/share/xivo-certs
ADD ./contribs/docker/certs /usr/share/xivo-certs
WORKDIR /usr/src/xivo-ctid-ng

RUN pip install -r requirements.txt
RUN python setup.py install
RUN cp -av etc/xivo-ctid-ng /etc
RUN mkdir /etc/xivo-ctid-ng/conf.d
RUN touch /var/log/xivo-ctid-ng.log
RUN chown www-data /var/log/xivo-ctid-ng.log
RUN mkdir /var/run/xivo-ctid-ng/
RUN chown www-data /var/run/xivo-ctid-ng/

RUN rm -fr /usr/src/xivo-ctid-ng

EXPOSE 9500

CMD xivo-ctid-ng -f -d
