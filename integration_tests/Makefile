.PHONY: test-setup egg-info test

test-setup: build-ctid-ng
	docker pull python:2.7
	docker pull p0bailey/docker-flask
	docker pull n3llyb0y/wait
	docker pull quintana/asterisk
	docker pull xivo/xivo-amid
	docker build -t ari-mock -f docker/Dockerfile-ari-mock .

build-ctid-ng: egg-info
	docker build -t xivo/xivo-ctid-ng ..
	docker build --no-cache -t xivo-ctid-ng-test -f docker/Dockerfile-ctid-ng-test ..


egg-info:
	cd .. && python setup.py egg_info

test:
	nosetests
