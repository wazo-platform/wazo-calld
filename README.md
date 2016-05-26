XiVO CTI NG [![Build Status](https://travis-ci.org/xivo-pbx/xivo-ctid-ng.png?branch=master)](https://travis-ci.org/xivo-pbx/xivo-ctid-ng)
===========

XiVO CTI is a [Computer telephony integration](http://en.wikipedia.org/Computer_telephony_integration) server 
that provides advanced telephony services such as automatic phone control and 
[Call center](http://en.wikipedia.org/wiki/Call_center) monitoring. CTI services are controlled by connecting to 
the server with the [XiVO CTI client](https://github.com/xivo-pbx/xivo-client-qt)

Installing XiVO CTI NG
----------------------

The server is already provided as a part of [XiVO](http://documentation.xivo.io).
Please refer to [the documentation](http://documentation.xivo.io/en/stable/installation/installsystem.html) for
further details on installing one.

Running unit tests
------------------

1. Install requirements with ```pip install -r requirements.txt -r test-requirements.txt```
2. Run tests with ```nosetests xivo_ctid_ng```

Running integration tests
-------------------------

You need Docker installed on your machine.

1. ```cd integration_tests```
2. ```pip install -r test-requirements.txt```
3. ```make test-setup```
4. ```make test```

Environment variables
---------------------

Running the integration tests is controlled by the following environment variables:

* `INTEGRATION_TEST_TIMEOUT`: controls the startup timeout of each container
