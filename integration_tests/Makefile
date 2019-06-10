CHAN_TEST_DIR ?= ../../chan-test

.PHONY: test-setup build-calld build-ari docker-pull egg-info test

test-setup: build-calld build-ari docker-pull

build-calld: docker-pull egg-info
	docker build -t wazopbx/wazo-calld ..
	docker build --no-cache -t wazo-calld-test -f docker/Dockerfile-calld-test ..
	docker build -t xivo-websocketd-mock -f docker/Dockerfile-websocketd-mock .

build-ari: docker-pull
	test -d $(CHAN_TEST_DIR)
	docker build -t ari-mock -f docker/Dockerfile-ari-mock .
	docker build -t ari-real -f $(CHAN_TEST_DIR)/Dockerfile $(CHAN_TEST_DIR)

docker-pull:
	docker pull p0bailey/docker-flask
	docker pull python:2.7.13-stretch
	docker pull swaggerapi/swagger-validator
	docker pull wazopbx/wait
	docker pull wazopbx/asterisk
	docker pull wazopbx/xivo-amid
	docker pull wazopbx/wazo-auth-mock
	docker pull wazopbx/wazo-confd-mock

clean:
	docker rmi -f wazopbx/wazo-calld
	docker rmi -f wazo-calld-test
	docker rmi -f ari-mock
	docker rmi -f ari-real

egg-info:
	cd .. && python setup.py egg_info

test:
	nosetests -x
