PROJECT_NAME=hostpoller
COMMIT_HASH=$(shell git rev-parse --short HEAD 2> /dev/null)
ifeq ($(COMMIT_HASH),)
  IMAGE_TAG := init
else
  IMAGE_TAG=$(COMMIT_HASH)
endif
IMAGE_NAME=$(PROJECT_NAME):$(IMAGE_TAG)
WORK_DIR=$(PWD)
LISTEN_IP=0.0.0.0
LISTEN_PORT=9000
MONITOR_PERIOD=0
POLLING_FREQUENCY=.5
REQUEST_TIMEOUT=5
TARGET=https://localhost
SOURCE_CONTAINER_TAG=3.9-slim-buster
PYTHONPATH=src/hostpoller/

export PYTHONPATH

.git/hooks/pre-commit:
	@pre-commit install

pytype.cfg:
	@poetry run pytype --generate-config pytype.cfg

build:
	@echo "Building container: $(IMAGE_NAME) Listen port: $(LISTEN_PORT)"
	#@docker build . #--no-cache
	@docker build . \
		--build-arg SOURCE_CONTAINER_TAG=$(SOURCE_CONTAINER_TAG) \
		--build-arg PROJECT_NAME=$(PROJECT_NAME) \
		--build-arg LISTEN_IP=$(LISTEN_IP) \
		--build-arg LISTEN_PORT=$(LISTEN_PORT) \
		--build-arg MONITOR_PERIOD=$(MONITOR_PERIOD) \
		--build-arg POLLING_FREQUENCY=$(POLLING_FREQUENCY) \
		--build-arg REQUEST_TIMEOUT=$(REQUEST_TIMEOUT) \
		--build-arg TARGET=$(TARGET) \
		-t $(IMAGE_NAME)
run:
	@echo "Running container: $(IMAGE_NAME) Listen IP: $(LISTEN_IP)"
	@docker run -it \
		--env "LISTEN_IP=$(LISTEN_IP)" \
		--env "LISTEN_PORT=$(LISTEN_PORT)" \
		--env "MONITOR_PERIOD=$(MONITOR_PERIOD)" \
		--env "POLLING_FREQUENCY=$(POLLING_FREQUENCY)" \
		--env "REQUEST_TIMEOUT=$(REQUEST_TIMEOUT)" \
		--env "TARGET=$(TARGET)" \
		--expose $(LISTEN_PORT) $(IMAGE_NAME)

inspect:
	@docker inspect $(IMAGE_NAME) | jq .

requirements.txt:
	@poetry export -o requirements.txt

deps: requirements.txt .git/hooks/pre-commit pytype.cfg
	@pip install -r $^

../$(PROJECT_NAME).tgz:
	@tar --exclude='.git*' --exclude="*.db" --exclude=".pre-commit-*" --exclude="poetry.lock" --exclude="*__pycache__" -czvf $@ ./
