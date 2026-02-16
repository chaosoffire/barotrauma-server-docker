"""
Universal Barotrauma Server Configuration Script.

A generic env-to-XML mapper. The script reads environment variables with
S.* and C.* prefixes and writes them into serversettings.xml and
clientpermissions.xml respectively. No game-specific defaults or attribute
names are hardcoded — users control their own config entirely via env vars.

Convention:
    S.*                          -> serversettings.xml attributes/children
    C.Client.<RuleID>.<Attr>     -> clientpermissions.xml <Client> entries
    C.FORCE_OVERRIDES=true       -> re-apply client permissions on restart

Design: Strict & Simple — pure functions + dataclasses, no class abstractions.
"""

import os
import sys
import xml.etree.ElementTree as ET
import logging
import tempfile
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# --- 1. Domain Models (Dataclasses for type safety) ---

@dataclass
class ServerSetting:
    """Represents a single setting for serversettings.xml."""
    key: str
    value: str
    path: List[str] = field(default_factory=list)  # e.g. ["campaignsettings"] for nested

@dataclass
class ClientPermissionRule:
    """Represents a rule to configure a Client in clientpermissions.xml."""
    rule_id: str
    account_id: str
    name: Optional[str] = None
    permissions: Optional[str] = None
    commands: List[str] = field(default_factory=list)
    extra_attributes: Dict[str, str] = field(default_factory=dict)

# --- 2. Pure Domain Logic: Environment Parsing ---

def parse_server_settings(env: Dict[str, str]) -> List[ServerSetting]:
    """
    Parses environment variables starting with 'S.' into ServerSetting objects.
    Pure function: Dict -> List[Data]

    Format:
        S.Key=Value            -> path=[], key=Key
        S.Child.Key=Value      -> path=[Child], key=Key
        S.A.B.C.Key=Value      -> path=[A,B,C], key=Key
    """
    settings = []
    for key, value in env.items():
        if not key.startswith("S."):
            continue

        parts = key.split(".")
        if len(parts) < 2 or not parts[-1]:
            continue

        if len(parts) == 2:
            settings.append(ServerSetting(key=parts[1], value=value))
        else:
            settings.append(ServerSetting(key=parts[-1], value=value, path=parts[1:-1]))

    return settings

def parse_client_permissions(env: Dict[str, str]) -> List[ClientPermissionRule]:
    """
    Parses environment variables starting with 'C.Client.' into ClientPermissionRule objects.
    Pure function: Dict -> List[Data]. Does NOT mutate input.

    Format: C.Client.<RuleID>.<Attr>=Value
    """
    raw_rules: Dict[str, Dict[str, str]] = {}

    for key, value in env.items():
        if not key.startswith("C.Client."):
            continue

        parts = key.split(".")
        if len(parts) < 4:
            continue

        rule_id = parts[2]
        attr = parts[3]

        if rule_id not in raw_rules:
            raw_rules[rule_id] = {}
        raw_rules[rule_id][attr] = value

    rules = []
    for rule_id, raw_props in raw_rules.items():
        props = dict(raw_props)  # Shallow copy — never mutate input

        if "accountid" not in props:
            logging.warning(f"Rule '{rule_id}' missing 'accountid'. Skipping.")
            continue

        commands = []
        if "commands" in props:
            commands = [c.strip() for c in props["commands"].split(",") if c.strip()]
            del props["commands"]

        account_id = props.pop("accountid")
        name = props.pop("name", None)
        permissions = props.pop("permissions", None)

        rules.append(ClientPermissionRule(
            rule_id=rule_id,
            account_id=account_id,
            name=name,
            permissions=permissions,
            commands=commands,
            extra_attributes=props,
        ))

    return rules

# --- 3. Pure Domain Logic: XML Manipulation ---

def apply_server_settings(root: ET.Element, settings: List[ServerSetting]) -> int:
    """
    Applies a list of ServerSetting to the XML root (upsert strategy).
    Returns count of changes.
    """
    updates = 0
    for setting in settings:
        target = root

        for tag in setting.path:
            next_node = target.find(tag)
            if next_node is None:
                next_node = ET.SubElement(target, tag)
                logging.info(f"Created new element <{tag}> inside <{target.tag}>")
            target = next_node

        target.set(setting.key, setting.value)
        display_value = "***" if "password" in setting.key.lower() else setting.value
        logging.info(f"Set {target.tag}.{setting.key} = '{display_value}'")
        updates += 1

    return updates

def apply_client_permissions(root: ET.Element, rules: List[ClientPermissionRule]) -> int:
    """
    Applies list of ClientPermissionRule to the XML root.
    Replace All Commands strategy — prevents drift.
    Returns count of changes.
    """
    updates = 0

    for rule in rules:
        target_client = None
        for client in root.findall("Client"):
            if client.get("accountid") == rule.account_id:
                target_client = client
                break

        is_new = False
        if target_client is None:
            logging.info(f"Creating new Client entry for {rule.account_id} (Rule: {rule.rule_id})")
            target_client = ET.SubElement(root, "Client")
            target_client.set("accountid", rule.account_id)
            is_new = True
        else:
            logging.info(f"Updating existing Client {rule.account_id} (Rule: {rule.rule_id})")

        if rule.permissions:
            target_client.set("permissions", rule.permissions)

        if rule.name:
            target_client.set("name", rule.name)
        elif is_new:
            target_client.set("name", rule.rule_id)

        for k, v in rule.extra_attributes.items():
            target_client.set(k, v)

        if rule.commands:
            for ec in target_client.findall("command"):
                target_client.remove(ec)
            for cmd_name in rule.commands:
                ET.SubElement(target_client, "command", name=cmd_name)

        updates += 1

    return updates

# --- 4. Infrastructure: File I/O ---

def load_xml(path: str) -> Tuple[Optional[ET.ElementTree], Optional[ET.Element]]:
    """Load and parse an XML file. Returns (None, None) on error."""
    if not os.path.exists(path):
        logging.warning(f"File not found: {path}")
        return None, None
    try:
        tree = ET.parse(path)
        return tree, tree.getroot()
    except ET.ParseError as e:
        logging.error(f"Failed to parse XML {path}: {e}")
        return None, None

def save_xml(tree: ET.ElementTree, path: str):
    """Writes XML to a temp file with fsync, then atomically replaces destination."""
    directory = os.path.dirname(os.path.abspath(path))

    if hasattr(ET, "indent"):  # Python 3.9+
        ET.indent(tree, space="  ", level=0)

    fd = None
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(dir=directory)
        with os.fdopen(fd, 'wb') as tf:
            tree.write(tf, encoding="utf-8", xml_declaration=True)
            tf.flush()
            os.fsync(tf.fileno())
        fd = None  # Closed by os.fdopen context manager
        os.replace(temp_path, path)
        logging.info(f"Saved {path}")
    except Exception as e:
        logging.error(f"Failed to save {path}: {e}")
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        raise

def touch_file(path: str):
    """Create or update timestamp of a marker file."""
    with open(path, 'a'):
        os.utime(path, None)

# --- 5. Configuration Orchestration ---

def configure_server(env: Dict[str, str], settings_path: str):
    """
    Server Settings — Continuous Enforcement.
    Always applies S.* env vars on every container start.
    """
    logging.info("--- Configuring Server Settings ---")
    settings = parse_server_settings(env)
    if not settings:
        logging.info("No S.* env vars found. Skipping server settings.")
        return

    tree, root = load_xml(settings_path)
    if root is None:
        logging.info(f"Creating new {settings_path}")
        root = ET.Element("serversettings")
        tree = ET.ElementTree(root)

    changes = apply_server_settings(root, settings)
    if changes > 0:
        save_xml(tree, settings_path)
    else:
        logging.info("No changes to server settings.")

def configure_clients(env: Dict[str, str], perms_path: str, marker_path: str):
    """
    Client Permissions — One-Time Seed.
    Applies C.Client.* env vars only once (or when C.FORCE_OVERRIDES=true).
    Preserves runtime changes (bans, karma, etc.) on subsequent restarts.
    """
    logging.info("--- Configuring Client Permissions ---")

    force = env.get("C.FORCE_OVERRIDES", "false").lower() == "true"
    already_applied = os.path.exists(marker_path)

    if already_applied and not force:
        logging.info(
            "Client permissions already initialized, skipping to preserve "
            "runtime changes. Set C.FORCE_OVERRIDES=true to bypass."
        )
        return

    rules = parse_client_permissions(env)
    if not rules:
        logging.info("No C.Client.* env vars found. Skipping client permissions.")
        return

    tree, root = load_xml(perms_path)
    if root is None:
        logging.info(f"Creating new {perms_path}")
        root = ET.Element("ClientPermissions")
        tree = ET.ElementTree(root)

    changes = apply_client_permissions(root, rules)
    if changes > 0:
        save_xml(tree, perms_path)
        touch_file(marker_path)
        logging.info(f"Created marker {marker_path}")
    else:
        logging.info("No changes to client permissions.")

# --- 6. Main Entry Point ---

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(message)s',
        stream=sys.stdout,
    )

    env = os.environ.copy()
    server_settings_file = env.get("MNT_SERVERSETTINGS", "serversettings.xml")
    client_perms_file = env.get("MNT_CLIENTPERM", "clientpermissions.xml")
    marker_file = ".client_perms_applied"

    failures = 0
    try:
        configure_server(env, server_settings_file)
    except Exception as e:
        logging.error(f"Server settings configuration failed: {e}", exc_info=True)
        failures += 1

    try:
        configure_clients(env, client_perms_file, marker_file)
    except Exception as e:
        logging.error(f"Client permissions configuration failed: {e}", exc_info=True)
        failures += 1

    if failures > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
