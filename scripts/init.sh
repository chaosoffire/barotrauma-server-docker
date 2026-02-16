#!/bin/sh
set -euo pipefail
echo "\e[0;32m*****STARTING INSTALL/UPDATE*****\e[0m"
mkdir -p "${GAMEPATH}"
chown -R steam:steam "${GAMEPATH}"
/home/steam/steamcmd/steamcmd.sh +force_install_dir "${GAMEPATH}" +login anonymous +app_update 1026340 validate +quit

if [ "${INSTALL_LUA}" = true ] ; then
    echo "\e[0;32m*****INSTALLING SERVERSIDE LUA*****\e[0m"
    wget -q https://github.com/evilfactory/LuaCsForBarotrauma/releases/download/latest/luacsforbarotrauma_patch_linux_server.tar.gz
    tar -xzf luacsforbarotrauma_patch_linux_server.tar.gz -C "${GAMEPATH}"
fi

echo "\e[0;32m*****INSTALL/UPDATE COMPLETE*****\e[0m"

mkdir -p "${MOUNTPATH}/config"
mkdir -p "${MOUNTPATH}/submarines"
mkdir -p "${MOUNTPATH}/saves"
mkdir -p "${MOUNTPATH}/mods"


SERVERSETTINGS="${GAMEPATH}/serversettings.xml"
PLAYERSETTINGS="${GAMEPATH}/config_player.xml"
CLIENTPERM="${GAMEPATH}/Data/clientpermissions.xml"

export MNT_SERVERSETTINGS="${MOUNTPATH}/config/serversettings.xml"
MNT_PLAYERSETTINGS="${MOUNTPATH}/config/config_player.xml"
export MNT_CLIENTPERM="${MOUNTPATH}/config/clientpermissions.xml"

# Copy vanilla serversettings if missing in volume
if [ ! -f "${MNT_SERVERSETTINGS}" ] ; then
    echo "Initializing serversettings.xml from vanilla default..."
    if [ -f "${SERVERSETTINGS}" ]; then
        cp "${SERVERSETTINGS}" "${MNT_SERVERSETTINGS}"
    else
        echo "Warning: Vanilla serversettings.xml not found at ${SERVERSETTINGS}"
        exit 1
    fi
fi

# Copy vanilla clientpermissions if missing in volume
if [ ! -f "${MNT_CLIENTPERM}" ] ; then
    echo "Initializing clientpermissions.xml from vanilla default..."
    if [ -f "${CLIENTPERM}" ]; then
        cp "${CLIENTPERM}" "${MNT_CLIENTPERM}"
    else
         echo "Warning: Vanilla clientpermissions.xml not found at ${CLIENTPERM}"
         exit 1
    fi
fi

# Copy vanilla config_player.xml if missing in volume
if [ ! -f "${MNT_PLAYERSETTINGS}" ] ; then
    echo "Initializing config_player.xml from vanilla default..."
    if [ -f "${PLAYERSETTINGS}" ]; then
        cp "${PLAYERSETTINGS}" "${MNT_PLAYERSETTINGS}"
    else
        echo "Warning: Vanilla config_player.xml not found at ${PLAYERSETTINGS}, skipping."
    fi
fi

# Apply Universal Configuration via Python
echo "Applying Universal Configuration..."
python3 /home/steam/server/configure.py

rm -f "${SERVERSETTINGS}"
rm -f "${CLIENTPERM}"
rm -f "${PLAYERSETTINGS}"

ln -s "${MNT_SERVERSETTINGS}" "${SERVERSETTINGS}"
ln -s "${MNT_PLAYERSETTINGS}" "${PLAYERSETTINGS}"
ln -s "${MNT_CLIENTPERM}" "${CLIENTPERM}"


mkdir -p "${GAMEPATH}/Submarines/Added/."
mkdir -p "${SAVEPATH}"
mkdir -p "${MODPATH}"

cp -nR "${GAMEPATH}/Submarines/Added/." "${MOUNTPATH}/submarines"
cp -nR "${SAVEPATH}/."                  "${MOUNTPATH}/saves"
cp -nR "${MODPATH}/."                   "${MOUNTPATH}/mods"

rm -rf "${GAMEPATH}/Submarines/Added"
rm -rf "${SAVEPATH}"
rm -rf "${MODPATH}"

ln -sf "${MOUNTPATH}/submarines"        "${GAMEPATH}/Submarines/Added"
ln -sf "${MOUNTPATH}/saves"             "${SAVEPATH}"
ln -sf "${MOUNTPATH}/mods"              "${MODPATH}"

./start.sh