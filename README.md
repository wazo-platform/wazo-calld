XiVO CTI [![Build Status](https://travis-ci.org/xivo-pbx/xivo-ctid.png?branch=master)](https://travis-ci.org/xivo-pbx/xivo-ctid)
========

XiVO CTI is a [Computer telephony integration](http://en.wikipedia.org/Computer_telephony_integration) server 
that provides advanced telephony services such as automatic phone control and 
[Call center](http://en.wikipedia.org/wiki/Call_center) monitoring. CTI services are controlled by connecting to 
the server with the [XiVO CTI client](https://github.com/xivo-pbx/xivo-client-qt)

Installing XiVO CTI
-------------------

The server is already provided as a part of [XiVO](http://documentation.xivo.io).
Please refer to [the documentation](http://documentation.xivo.io/en/stable/installation/installsystem.html) for
further details on installing one.

Running unit tests
------------------

1. Install requirements with ```pip install -r requirements.txt```
2. Run tests with ```nosetests xivo_ctid```
