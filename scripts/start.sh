#!/bin/sh
set -euo pipefail
echo "\e[0;32m*****STARTING SERVER*****\e[0m"
cd "${GAMEPATH}"
exec ./DedicatedServer
