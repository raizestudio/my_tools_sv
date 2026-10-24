#!/bin/bash

HOST="localhost"
PORT="5432"
TIMEOUT=30

echo "Waiting for PostgreSQL at $HOST:$PORT in CI..."

for i in $(seq 1 $TIMEOUT); do
    if nc -z -w 1 "$HOST" "$PORT" &> /dev/null; then
        echo "PostgreSQL is available on CI!"
        exit 0
    fi
    sleep 1
done

echo "Error: PostgreSQL did not become available within $TIMEOUT seconds."
exit 1
