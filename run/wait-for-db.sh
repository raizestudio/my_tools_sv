#!/bin/sh
wait-for-db.sh: Waits for PostgreSQL to be available via TCP

HOST="db"
PORT="5432"
TIMEOUT=30 # Total seconds to wait

echo "Waiting for PostgreSQL at $HOST:$PORT..."

for i in $(seq $TIMEOUT); do
Use 'nc' (netcat) to check if the port is open.
nc -z: Zero-I/O mode (just report status).
nc -w 1: Timeout after 1 second.

if nc -z -w 1 $HOST $PORT; then
echo "PostgreSQL is available! Starting application."
exit 0
fi
sleep 1
done

echo "Error: PostgreSQL did not become available within $TIMEOUT seconds."
exit 1
