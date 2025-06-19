<p align="center"><img src="https://github.com/wazo-platform/wazo-platform.org/raw/master/static/images/logo.png" height="200"></p>

# wazo-calld

[![Build Status](https://jenkins.wazo.community/buildStatus/icon?job=wazo-calld)](https://jenkins.wazo.community/job/wazo-calld)

wazo-calld provides REST API to create, control calls and hangup calls, and sends events when something happens to a call.

## Installing wazo-calld

The server is already provided as a part of [Wazo Platform](https://wazo-platform.org/uc-doc/).
Please refer to [the documentation](https://wazo-platform.org/uc-doc/installation/installsystem) for
further details on installing one.

## Usage

On a Wazo Platform environment, wazo-calld is launched automatically at system boot via a systemd service.

## Testing

### Running unit tests

```
pip install tox
tox --recreate -e py39
```

### Running integration tests

You need Docker installed on your machine.

1. ```cd integration_tests```
2. ```pip install -r test-requirements.txt```
3. ```git clone https://github.com/wazo-platform/chan-test```
4. ```export CHAN_TEST_DIR=$PWD/chan-test   # CHAN_TEST_DIR defaults to ../../chan-test```
5. ```make test-setup```
6. ```make test```

### Environment variables

Running the integration tests is controlled by the following environment variables:

* `INTEGRATION_TEST_TIMEOUT`: controls the startup timeout of each container
* `LOCAL_GIT_REPOS`: may be used to mount development python packages inside containers

## How to get help

If you ever need help from the Wazo Platform community, the following resources are available:

* [Discourse](https://wazo-platform.discourse.group/)
* [Mattermost](https://mm.wazo.community)

## Contributing

You can learn more on how to contribute in the [Wazo Platform documentation](https://wazo-platform.org/contribute/code).

## License

wazo-calld is released under the GPL 3.0 license. You can get the full license in the [LICENSE](LICENSE) file.
do not merge
