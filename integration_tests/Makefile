ifeq ($(CHAN_TEST_DIR),)
	CHAN_TEST_TARGET=chan-test-pull
else
	CHAN_TEST_TARGET=chan-test-build
endif

test-setup: build-calld build-ari build-call-logd

build-calld: egg-info
	docker build --no-cache -t wazoplatform/wazo-calld ..
	docker build --no-cache -t wazo-calld-test -f docker/Dockerfile-calld-test ..

build-ari: ari-mock chan-test

ari-mock:
	docker build -t ari-mock -f docker/Dockerfile-ari-mock .

chan-test: $(CHAN_TEST_TARGET)

chan-test-pull:
	docker pull wazoplatform/chan-test
	docker tag wazoplatform/chan-test:latest ari-real

chan-test-build:
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

.PHONY: test-setup build-calld build-ari ari-mock chan-test chan-test-pull chan-test-build build-call-logd egg-info test
