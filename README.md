# Barotrauma Server Docker

This is a Dockerized version of the [Barotrauma](https://store.steampowered.com/app/602960/Barotrauma/) dedicated server.

## Features

- **Universal Configuration**: Configure _any_ server setting or client permission via Environment Variables. No more editing XML files manually.
- **Automatic Updates**: Updates Barotrauma on startup via SteamCMD.
- **LuaFs Support**: Optional installation of LuaCsForBarotrauma.

## Quick Start (Docker Compose)

This repository includes an example [docker-compose.yml](example/docker-compose.yml) file you can use to setup your server.

```yaml
services:
  barotrauma:
    image: ghcr.io/chaosoffire/barotrauma-server-docker
    restart: unless-stopped
    container_name: barotrauma-server
    ports:
      - 27015:27015/udp
      - 27016:27016/udp
    environment:
      # Server Settings (Prefix S.)
      - S.ServerName=Deep Sea Station
      - S.Password=secret123
      - S.MaxPlayers=12
      - S.VoiceChatEnabled=true

      # Client Permissions (Prefix C.Client.<RuleID>)
      - C.Client.Owner.accountid=STEAM_0:1:12345678
      - C.Client.Owner.permissions=All
      - C.Client.Owner.commands=console,heal,spawn

      # Optional: Force re-apply permissions on restart
      # - C.FORCE_OVERRIDES=true
    volumes:
      - ./barotrauma_data:/barotrauma
```

## Configuration

This image uses a dynamic configuration script (`configure.py`) that maps Environment Variables to the game's XML configuration files.

### 1. Server Settings (`serversettings.xml`)

Prefix any environment variable with `S.` to set a value in `serversettings.xml`.

- **Strategy**: **Continuous Enforcement**. These settings are re-applied every time the container starts.
- **Syntax**: `S.AttributeName=Value` or `S.ChildNode.AttributeName=Value`.

| Environment Variable    | XML Equivalent                                               | Description                           |
| :---------------------- | :----------------------------------------------------------- | :------------------------------------ |
| `S.ServerName=MyServer` | `<serversettings ServerName="MyServer" ... />`               | Sets the server name.                 |
| `S.Password=12345`      | `<serversettings Password="12345" ... />`                    | Sets the server password.             |
| `S.Physics.Gravity=0.5` | `<serversettings><Physics Gravity="0.5" /></serversettings>` | Nested configuration (e.g., Physics). |

### 2. Client Permissions (`clientpermissions.xml`)

Prefix variables with `C.Client.` to configure administrative privileges.

- **Strategy**: **One-Time Seed**. These will be applied **only if** `clientpermissions.xml` (or a marker file) does not exist (first run). This prevents the container from overwriting in-game bans or rank changes on restart.
- **Force Update**: Set `C.FORCE_OVERRIDES=true` to force strict enforcement on every restart (warning: this will wipe any in-game changes not present in env vars).

**Syntax**: `C.Client.<UniqueRuleID>.<Attribute>=Value`

| Environment Variable                 | Description                                                          |
| :----------------------------------- | :------------------------------------------------------------------- |
| `C.Client.Admin.accountid=STEAM_...` | SteamID64 or SteamID to grant permissions to.                        |
| `C.Client.Admin.permissions=All`     | Permission set (None, All, or comma-separated list like `Kick,Ban`). |
| `C.Client.Admin.commands=heal,spawn` | Specific console commands allowed for this user.                     |
| `C.Client.Admin.name=MyName`         | (Optional) Name label for the client.                                |

## Volumes and Persistence

Mount a volume to `/barotrauma` to persist your server data.

| Container Path           | Description                                                      |
| :----------------------- | :--------------------------------------------------------------- |
| `/barotrauma/config`     | Configuration files (serversettings.xml, clientpermissions.xml). |
| `/barotrauma/saves`      | Campaign save files.                                             |
| `/barotrauma/submarines` | Custom submarines.                                               |
| `/barotrauma/mods`       | Workshop mods.                                                   |

## Ports

| Port    | Type | Description      |
| :------ | :--- | :--------------- |
| `27015` | UDP  | Game Port        |
| `27016` | UDP  | Steam Query Port |

## Advanced: LuaCsForBarotrauma

To install LuaCsForBarotrauma (server-side Lua), set the environment variable:
`INSTALL_LUA=true`

## Reporting Issues/Feature Requests

Issues/Feature requests can be submitted by using [this link](https://github.com/chaosoffire/barotrauma-server-docker/issues/new/choose).
