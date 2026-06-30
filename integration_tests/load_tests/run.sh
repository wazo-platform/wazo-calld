#!/bin/bash
# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Bring up the real_asterisk integration stack and run the ARI connection-pool
# exhaustion load test against it with Locust.

set -euo pipefail

LOAD_TEST_DIR=$(cd "$(dirname "$0")" && pwd)
INTEGRATION_DIR=$(cd "$LOAD_TEST_DIR/.." && pwd)
ASSETS_DIR="$INTEGRATION_DIR/assets"
COMPOSE_PROJECT_NAME="calld-loadtest"
COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.real_asterisk.override.yml -f docker-compose.load_test.override.yml)

compose() {
    (cd "$ASSETS_DIR" && docker compose -p "$COMPOSE_PROJECT_NAME" "${COMPOSE_FILES[@]}" "$@")
}

host_port() {
    local service="$1" container_port="$2" mapping
    mapping=$(compose port "$service" "$container_port")
    echo "${mapping##*:}"
}

build_images() {
    local chan_test_dir="$1"
    echo ">>> Building integration images (CHAN_TEST_DIR=$chan_test_dir)"
    make -C "$INTEGRATION_DIR" test-setup CHAN_TEST_DIR="$chan_test_dir"
}

start_stack() {
    echo ">>> Starting real_asterisk stack"
    INTEGRATION_TEST_TIMEOUT="${INTEGRATION_TEST_TIMEOUT:-60}" compose up -d
    echo ">>> Waiting for services to be ready"
    compose run --rm sync
}

stop_stack() {
    echo ">>> Stopping stack"
    compose down --volumes --remove-orphans
}

run_locust() {
    local calld_port auth_port rabbitmq_port ari_port
    calld_port=$(host_port calld 9500)
    auth_port=$(host_port auth 9497)
    rabbitmq_port=$(host_port rabbitmq 5672)
    ari_port=$(host_port ari 5039)

    echo ">>> calld=$calld_port auth=$auth_port rabbitmq=$rabbitmq_port ari=$ari_port"

    export CALLD_HOST=127.0.0.1 CALLD_PORT="$calld_port"
    export AUTH_HOST=127.0.0.1 AUTH_PORT="$auth_port"
    export RABBITMQ_HOST=127.0.0.1 RABBITMQ_PORT="$rabbitmq_port"
    export ARI_URL="http://127.0.0.1:$ari_port"
    export CHANNEL_COUNT="${CHANNEL_COUNT:-20}"

    echo ">>> Watch wazo-calld for pool exhaustion in another shell:"
    echo "    cd $ASSETS_DIR && docker compose -p $COMPOSE_PROJECT_NAME ${COMPOSE_FILES[*]} logs -f calld | grep -i 'connection pool is full'"

    (cd "$LOAD_TEST_DIR" && locust -f locustfile.py --host "http://127.0.0.1:$calld_port" "${LOCUST_ARGS[@]}")
}

usage() {
    cat <<'EOF'
Usage: run.sh [--build [CHAN_TEST_DIR]] [--keep-up] [-- LOCUST_ARGS...]

  --build [DIR]   Build integration images first (make test-setup).
                  DIR defaults to $CHAN_TEST_DIR or ~/wazo/chan-test.
  --keep-up       Leave the docker stack running after Locust exits.
  -- ...          Remaining args are passed to locust (e.g. headless run:
                  -- --headless -u 30 -r 5 -t 2m).

Env knobs: CHANNEL_COUNT, INTEGRATION_TEST_TIMEOUT, DIAL_AOR.
EOF
}

main() {
    local do_build=false keep_up=false
    local chan_test_dir="${CHAN_TEST_DIR:-$HOME/wazo/chan-test}"
    LOCUST_ARGS=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --build)
                do_build=true
                if [[ ${2:-} && ${2:-} != -* ]]; then
                    chan_test_dir="$2"
                    shift
                fi
                ;;
            --keep-up) keep_up=true ;;
            --) shift; LOCUST_ARGS=("$@"); break ;;
            -h|--help) usage; return 0 ;;
            *) echo "Unknown argument: $1" >&2; usage; return 1 ;;
        esac
        shift
    done

    if [[ "$keep_up" == false ]]; then
        trap stop_stack EXIT
    fi

    if [[ "$do_build" == true ]]; then
        build_images "$chan_test_dir"
    fi

    start_stack
    run_locust
}

main "$@"
