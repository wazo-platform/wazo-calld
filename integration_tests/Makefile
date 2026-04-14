CHAN_TEST_DIR ?= ../../chan-test

test-setup: build-calld build-ari build-call-logd

build-calld: egg-info
	docker build -t wazoplatform/wazo-calld ..
	docker build --no-cache -t wazo-calld-test -f docker/Dockerfile-calld-test ..

build-ari:
	test -d $(CHAN_TEST_DIR)
	docker build -t ari-mock -f docker/Dockerfile-ari-mock .
	docker build -t ari-real --pull -f $(CHAN_TEST_DIR)/Dockerfile $(CHAN_TEST_DIR)

build-call-logd:
	docker build --pull -t call-logd-test -f docker/Dockerfile-call-logd-test .
	docker build --pull -t call-logd-db-test -f docker/Dockerfile-call-logd-db .

clean:
	docker rmi -f wazoplatform/wazo-calld
	docker rmi -f wazo-calld-test
	docker rmi -f ari-mock
	docker rmi -f ari-real
	docker rmi -f call-logd-test
	docker rmi -f call-logd-db-test

egg-info:
	cd .. && python setup.py egg_info

test:
	pytest

.PHONY: test-setup build-calld build-ari build-call-logd egg-info test
