#!/bin/sh
set -eu

umask 027

for runtime_dir in \
    /app/data \
    /app/runs \
    /app/kb/chroma \
    /app/kb/docs
do
    if ! mkdir -p "${runtime_dir}"; then
        echo "docker entrypoint: cannot create ${runtime_dir}" >&2
        exit 1
    fi

    if [ ! -w "${runtime_dir}" ]; then
        echo "docker entrypoint: ${runtime_dir} is not writable by uid $(id -u)" >&2
        exit 1
    fi
done

echo "docker entrypoint: initializing database"
python -m src.app.db

echo "docker entrypoint: starting application"
exec "$@"
