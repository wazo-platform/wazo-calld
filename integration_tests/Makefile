CHAN_TEST_DIR ?= ../../chan-test

.PHONY: test-setup build-ctid-ng build-ari docker-pull egg-info test

test-setup: build-ctid-ng build-ari docker-pull

build-ctid-ng: docker-pull egg-info
	docker build -t wazopbx/xivo-ctid-ng ..
	docker build --no-cache -t xivo-ctid-ng-test -f docker/Dockerfile-ctid-ng-test ..
	docker build -t xivo-websocketd-mock -f docker/Dockerfile-websocketd-mock .

build-ari: docker-pull
	test -d $(CHAN_TEST_DIR)
	docker build -t ari-mock -f docker/Dockerfile-ari-mock .
	docker build -t ari-real -f $(CHAN_TEST_DIR)/Dockerfile $(CHAN_TEST_DIR)

docker-pull:
	docker pull mongooseim/mongooseim:2.1.0
	docker pull n3llyb0y/wait
	docker pull waisbrot/wait
	docker pull p0bailey/docker-flask
	docker pull postgres:9.6
	docker pull python:2.7
	docker pull swaggerapi/swagger-validator
	docker pull wazopbx/asterisk
	docker pull wazopbx/xivo-amid

clean:
	docker rmi -f wazopbx/xivo-ctid-ng
	docker rmi -f xivo-ctid-ng-test
	docker rmi -f ari-mock
	docker rmi -f ari-real

egg-info:
	cd .. && python setup.py egg_info

test:
	nosetests -x
