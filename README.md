# wazo-calld [![Build Status](https://jenkins.wazo.community/buildStatus/icon?job=wazo-calld)](https://jenkins.wazo.community/job/wazo-calld)

wazo-calld provides REST API to create, control calls and hangup calls, and sends events when something happens to a call.

## Installing wazo-calld

The server is already provided as a part of [Wazo](http://documentation.wazo.community).
Please refer to [the documentation](http://documentation.wazo.community/en/stable/installation/installsystem.html) for
further details on installing one.

## Running unit tests

```
pip install tox
tox --recreate -e py37
```

## Running integration tests

You need Docker installed on your machine.

1. ```cd integration_tests```
2. ```pip install -r test-requirements.txt```
3. ```git clone https://github.com/wazo-platform/chan-test```
4. ```export CHAN_TEST_DIR=$PWD/chan-test   # CHAN_TEST_DIR defaults to ../../chan-test```
4. ```make test-setup```
5. ```make test```

## Environment variables

Running the integration tests is controlled by the following environment variables:

* `INTEGRATION_TEST_TIMEOUT`: controls the startup timeout of each container
* `LOCAL_GIT_REPOS`: may be used to mount development python packages inside containers
