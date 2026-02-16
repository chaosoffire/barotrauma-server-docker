FROM cm2network/steamcmd
USER root
RUN dpkg --add-architecture i386; apt-get update; apt-get upgrade -y; apt-get install --no-install-recommends -y \
    libgcc1 \
    lib32stdc++6 \
    libicu-dev \
    wget \
    python3 \
    && apt-get clean autoclean  \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

USER steam
ENV MOUNTPATH=/barotrauma \
    GAMEPATH=/home/steam/server/barotrauma \
    INSTALL_LUA=
ENV SCRIPTPATH=${GAMEPATH}/scripts \
    SAVEPATH="${GAMEPATH}/Daedalic Entertainment GmbH/Barotrauma/Multiplayer" \
    WORKSHOPMODSPATH="${GAMEPATH}/Daedalic Entertainment GmbH/Barotrauma/WorkshopMods/Installed" \
    MODPATH="${GAMEPATH}/LocalMods" \
    MNT_SERVERSETTINGS="${MOUNTPATH}/config/serversettings.xml" \
    MNT_PLAYERSETTINGS="${MOUNTPATH}/config/config_player.xml" \
    MNT_CLIENTPERM="${MOUNTPATH}/config/clientpermissions.xml"
ENV ENTRYSCRIPT=${SCRIPTPATH}/dockerful-entry.sh

COPY --chown=steam:steam ./scripts/* /home/steam/server/
RUN chmod +x /home/steam/server/init.sh /home/steam/server/start.sh

WORKDIR /home/steam/server

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD timeout 3 bash -c '</dev/tcp/localhost/27015' || exit 1

EXPOSE 27015 27016
ENTRYPOINT ["/home/steam/server/init.sh"]