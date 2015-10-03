FROM debian:latest

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get -qq update
RUN apt-get -qq -y install apt-utils
RUN apt-get -qq -y install \
     build-essential \
     python \
     python-pip \
     git \
     libpq-dev \
     libldap2-dev \
     libsasl2-dev \
     libyaml-dev \
     python-dev 

WORKDIR /root/
ADD . /root/xivo-ctid
ADD ./contribs/docker/certs /usr/share/xivo-certs
WORKDIR /root/xivo-ctid

RUN pip install -r requirements.txt
RUN python setup.py install
RUN cp -av etc/xivo-ctid /etc
RUN mkdir /etc/xivo-ctid/conf.d
RUN touch /var/log/xivo-ctid.log
RUN chown www-data /var/log/xivo-ctid.log
RUN mkdir /var/run/xivo-ctid/
RUN chown www-data /var/run/xivo-ctid/

WORKDIR /root
RUN rm -fr /root/xivo-ctid

EXPOSE 9485

CMD xivo-ctid -f -d
