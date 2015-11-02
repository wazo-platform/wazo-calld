.PHONY: test-setup egg-info test

test-setup: egg-info
	docker pull python:2.7
	# docker pull nickstenning/flask
	docker pull p0bailey/docker-flask
	docker pull n3llyb0y/wait
	docker build -t xivo/xivo-ctid-ng ..
	docker build -t xivo-auth-mock -f docker/Dockerfile-auth-mock ..
	docker build -t xivo-ari-mock -f docker/Dockerfile-ari-mock ..
	docker build --no-cache -t xivo-ctid-ng-test -f docker/Dockerfile-ctid-ng-test ..

egg-info:
	cd .. && python setup.py egg_info

test:
	nosetests
