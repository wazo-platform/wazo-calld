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
WORKDIR /root/xivo-ctid
RUN pip install -r requirements.txt
RUN python setup.py install
RUN cp -av etc/xivo-ctid /etc
RUN mkdir /etc/xivo-ctid/conf.d

WORKDIR /root
RUN rm -fr /root/xivo-ctid

EXPOSE 5003
EXPOSE 9495

CMD xivo-ctid -f -d
