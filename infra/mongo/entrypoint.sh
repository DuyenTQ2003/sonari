#!/bin/sh
# MongoDB refuses --auth on a replica-set member without a keyfile, even with one member.
# One member has no peers to share it with, so a fresh random key per container start is
# enough. mongod insists the file is owned by its user and readable by nobody else.
set -eu

# A restarted container still has last run's key, owned by mongodb. Even root may not
# open that file for writing in the sticky /tmp (fs.protected_regular), so remove it first.
rm -f /tmp/mongo-keyfile
head -c 600 /dev/urandom | base64 -w0 > /tmp/mongo-keyfile
chown mongodb:mongodb /tmp/mongo-keyfile
chmod 400 /tmp/mongo-keyfile

# The image runs everything in this directory once, against an empty data directory.
cp /infra/mongo-init.js /docker-entrypoint-initdb.d/mongo-init.js

exec docker-entrypoint.sh "$@"
