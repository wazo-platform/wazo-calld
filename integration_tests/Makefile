CHAN_TEST_DIR ?= ../../chan-test

test-setup: build-calld build-ari

build-calld: egg-info
	docker build -t wazopbx/wazo-calld ..
	docker build --no-cache -t wazo-calld-test -f docker/Dockerfile-calld-test ..
	docker build -t xivo-websocketd-mock -f docker/Dockerfile-websocketd-mock .

build-ari:
	test -d $(CHAN_TEST_DIR)
	docker build -t ari-mock -f docker/Dockerfile-ari-mock .
	docker build -t ari-real --pull -f $(CHAN_TEST_DIR)/Dockerfile $(CHAN_TEST_DIR)

clean:
	docker rmi -f wazopbx/wazo-calld
	docker rmi -f wazo-calld-test
	docker rmi -f ari-mock
	docker rmi -f ari-real

egg-info:
	cd .. && python setup.py egg_info

test:
	pytest -x

.PHONY: test-setup build-calld build-ari egg-info test
