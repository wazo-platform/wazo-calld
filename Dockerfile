FROM python:3.7-slim-buster AS compile-image
LABEL maintainer="Wazo Maintainers <dev@wazo.community>"

RUN python -m venv /opt/venv
# Activate virtual env
ENV PATH="/opt/venv/bin:$PATH"

COPY . /usr/src/wazo-calld
WORKDIR /usr/src/wazo-calld
RUN pip install -r requirements.txt
RUN python setup.py install

FROM python:3.7-slim-buster AS build-image
COPY --from=compile-image /opt/venv /opt/venv

COPY ./etc/wazo-calld /etc/wazo-calld
COPY ./bin/wazo-pdf2fax /usr/bin/wazo-pdf2fax

RUN true \
    && apt-get -q update \
    && apt-get -yq install --no-install-recommends ghostscript \
    && adduser --quiet --system --group --home /var/lib/wazo-calld wazo-calld \
    && mkdir -p /etc/wazo-calld/conf.d \
    && install -o www-data -g www-data /dev/null /var/log/wazo-calld.log \
    && chown root:www-data /usr/bin/wazo-pdf2fax \
    && rm -fr /var/lib/apt/lists/*

EXPOSE 9500

# Activate virtual env
ENV PATH="/opt/venv/bin:$PATH"
CMD ["wazo-calld"]
