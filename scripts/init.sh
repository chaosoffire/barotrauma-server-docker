#!/bin/sh
set -euo pipefail
echo "\e[0;32m*****STARTING INSTALL/UPDATE*****\e[0m"
mkdir -p "${GAMEPATH}"
/home/steam/steamcmd/steamcmd.sh +force_install_dir "${GAMEPATH}" +login anonymous +app_update 1026340 validate +quit

if [ "${INSTALL_LUA}" = true ] ; then
    echo "\e[0;32m*****INSTALLING SERVERSIDE LUA*****\e[0m"
    wget -q https://github.com/evilfactory/LuaCsForBarotrauma/releases/download/latest/luacsforbarotrauma_patch_linux_server.tar.gz -O "${GAMEPATH}/lua_patch.tar.gz"
    tar -xzf "${GAMEPATH}/lua_patch.tar.gz" -C "${GAMEPATH}"
    rm -f "${GAMEPATH}/lua_patch.tar.gz"
fi

echo "\e[0;32m*****INSTALL/UPDATE COMPLETE*****\e[0m"

mkdir -p "${MOUNTPATH}/config"
mkdir -p "${MOUNTPATH}/submarines"
mkdir -p "${MOUNTPATH}/saves"
mkdir -p "${MOUNTPATH}/mods"

SERVERSETTINGS_TEMPLATE="/home/steam/server/serversettings.xml.template"
CLIENTPERM_TEMPLATE="/home/steam/server/clientpermissions.xml.template"

SERVERSETTINGS="${GAMEPATH}/serversettings.xml"
PLAYERSETTINGS="${GAMEPATH}/config_player.xml"
CLIENTPERM="${GAMEPATH}/Data/clientpermissions.xml"

# Copy vanilla serversettings if missing in volume
if [ ! -f "${MNT_SERVERSETTINGS}" ] ; then
    echo "Initializing serversettings.xml from template..."
    if [ -f "${SERVERSETTINGS_TEMPLATE}" ]; then
        cp "${SERVERSETTINGS_TEMPLATE}" "${MNT_SERVERSETTINGS}"
    else
        echo "Warning: Template serversettings.xml.template not found at ${SERVERSETTINGS_TEMPLATE}"
        exit 1
    fi
fi

# Copy vanilla clientpermissions if missing in volume
if [ ! -f "${MNT_CLIENTPERM}" ] ; then
    echo "Initializing clientpermissions.xml from template..."
    if [ -f "${CLIENTPERM_TEMPLATE}" ]; then
        cp "${CLIENTPERM_TEMPLATE}" "${MNT_CLIENTPERM}"
    else
         echo "Warning: Template clientpermissions.xml.template not found at ${CLIENTPERM_TEMPLATE}"
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
mkdir -p "${WORKSHOPMODSPATH}"

cp -nR "${GAMEPATH}/Submarines/Added/." "${MOUNTPATH}/submarines"
cp -nR "${SAVEPATH}/."                  "${MOUNTPATH}/saves"
cp -nR "${MODPATH}/."                   "${MOUNTPATH}/mods"

rm -rf "${GAMEPATH}/Submarines/Added"
rm -rf "${SAVEPATH}"
rm -rf "${MODPATH}"

ln -sf "${MOUNTPATH}/submarines"        "${GAMEPATH}/Submarines/Added"
ln -sf "${MOUNTPATH}/saves"             "${SAVEPATH}"
ln -sf "${MOUNTPATH}/mods"              "${MODPATH}"

exec ./start.sh