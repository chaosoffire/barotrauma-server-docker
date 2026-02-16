import sys
import os
import unittest
import shutil
import tempfile
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock

# Add scripts folder to path to import configure.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))

from configure import (
    ServerSetting, ClientPermissionRule,
    parse_server_settings, parse_client_permissions,
    apply_server_settings, apply_client_permissions,
    configure_server, configure_clients,
    save_xml, load_xml
)


class TestParseServerSettings(unittest.TestCase):
    """Tests for parse_server_settings() — pure env parsing."""

    def test_basic_and_nested(self):
        env = {
            "S.name": "TestServer",
            "S.Physics.Gravity": "0.5",
            "IGNORE.ME": "Ignored",
        }
        settings = parse_server_settings(env)

        self.assertEqual(len(settings), 2)

        s1 = next(s for s in settings if s.key == "name")
        self.assertEqual(s1.value, "TestServer")
        self.assertEqual(s1.path, [])

        s2 = next(s for s in settings if s.key == "Gravity")
        self.assertEqual(s2.value, "0.5")
        self.assertEqual(s2.path, ["Physics"])

    def test_empty_env(self):
        self.assertEqual(parse_server_settings({}), [])

    def test_no_matching_keys(self):
        env = {"FOO": "bar", "C.Client.X.name": "test"}
        self.assertEqual(parse_server_settings(env), [])

    def test_malformed_keys_skipped(self):
        env = {
            "S.": "no key",          # trailing dot, empty key
            "S": "no dot",           # no dot at all
            "S.valid": "ok",
        }
        settings = parse_server_settings(env)
        self.assertEqual(len(settings), 1)
        self.assertEqual(settings[0].key, "valid")

    def test_deeply_nested_path(self):
        env = {"S.A.B.C.Key": "Val"}
        settings = parse_server_settings(env)
        self.assertEqual(len(settings), 1)
        self.assertEqual(settings[0].path, ["A", "B", "C"])
        self.assertEqual(settings[0].key, "Key")

    def test_special_xml_chars_in_value(self):
        env = {"S.name": '<Test>&"Server"'}
        settings = parse_server_settings(env)
        self.assertEqual(settings[0].value, '<Test>&"Server"')


class TestParseClientPermissions(unittest.TestCase):
    """Tests for parse_client_permissions() — pure env parsing."""

    def test_basic_with_commands(self):
        env = {
            "C.Client.Admin.accountid": "STEAM_123",
            "C.Client.Admin.permissions": "All",
            "C.Client.Admin.commands": "kick,ban",
            "C.Client.Mod.accountid": "STEAM_456",
            "C.Client.Mod.rank": "Moderator",
            "C.Client.Invalid.permissions": "None",  # Missing accountid
        }
        rules = parse_client_permissions(env)

        self.assertEqual(len(rules), 2)

        admin = next(r for r in rules if r.rule_id == "Admin")
        self.assertEqual(admin.account_id, "STEAM_123")
        self.assertEqual(admin.permissions, "All")
        self.assertEqual(admin.commands, ["kick", "ban"])

        mod = next(r for r in rules if r.rule_id == "Mod")
        self.assertEqual(mod.extra_attributes["rank"], "Moderator")

    def test_does_not_mutate_input(self):
        env = {
            "C.Client.Owner.accountid": "STEAM_111",
            "C.Client.Owner.commands": "heal,spawn",
            "C.Client.Owner.name": "Boss",
        }
        env_copy = dict(env)
        parse_client_permissions(env)
        self.assertEqual(env, env_copy)

    def test_empty_env(self):
        self.assertEqual(parse_client_permissions({}), [])

    def test_malformed_keys_skipped(self):
        env = {
            "C.Client.": "incomplete",
            "C.Client": "no rule id",
            "C.": "just prefix",
        }
        self.assertEqual(parse_client_permissions(env), [])

    def test_commands_with_spaces_trimmed(self):
        env = {
            "C.Client.X.accountid": "STEAM_999",
            "C.Client.X.commands": " heal , spawn , revive ",
        }
        rules = parse_client_permissions(env)
        self.assertEqual(rules[0].commands, ["heal", "spawn", "revive"])

    def test_empty_commands_string(self):
        env = {
            "C.Client.X.accountid": "STEAM_999",
            "C.Client.X.commands": "",
        }
        rules = parse_client_permissions(env)
        self.assertEqual(rules[0].commands, [])

    def test_commands_only_commas(self):
        env = {
            "C.Client.X.accountid": "STEAM_999",
            "C.Client.X.commands": ",,, ,",
        }
        rules = parse_client_permissions(env)
        self.assertEqual(rules[0].commands, [])


class TestApplyServerSettings(unittest.TestCase):
    """Tests for apply_server_settings() — XML manipulation."""

    def test_create_update_nested(self):
        root = ET.Element("serversettings")
        ET.SubElement(root, "Physics")

        settings = [
            ServerSetting(key="name", value="NewName"),
            ServerSetting(key="Gravity", value="0.0", path=["Physics"]),
            ServerSetting(key="NewChildAttr", value="Value", path=["NewChild"]),
        ]

        changes = apply_server_settings(root, settings)

        self.assertEqual(changes, 3)
        self.assertEqual(root.get("name"), "NewName")
        self.assertEqual(root.find("Physics").get("Gravity"), "0.0")
        self.assertEqual(root.find("NewChild").get("NewChildAttr"), "Value")

    def test_empty_settings(self):
        root = ET.Element("serversettings")
        self.assertEqual(apply_server_settings(root, []), 0)

    def test_special_chars_preserved(self):
        root = ET.Element("serversettings")
        settings = [ServerSetting(key="name", value='<Test>&"Server"')]
        apply_server_settings(root, settings)
        self.assertEqual(root.get("name"), '<Test>&"Server"')

    def test_deeply_nested_creates_chain(self):
        root = ET.Element("serversettings")
        settings = [ServerSetting(key="Attr", value="V", path=["A", "B", "C"])]
        apply_server_settings(root, settings)

        node = root.find("A/B/C")
        self.assertIsNotNone(node)
        self.assertEqual(node.get("Attr"), "V")


class TestApplyClientPermissions(unittest.TestCase):
    """Tests for apply_client_permissions() — XML manipulation."""

    def test_update_existing_and_create_new(self):
        root = ET.Element("ClientPermissions")

        existing = ET.SubElement(root, "Client")
        existing.set("accountid", "STEAM_123")
        existing.set("name", "OldName")
        ET.SubElement(existing, "command", name="old_cmd")

        rules = [
            ClientPermissionRule(
                rule_id="Admin",
                account_id="STEAM_123",
                permissions="All",
                commands=["new_cmd"],
            ),
            ClientPermissionRule(
                rule_id="NewGuy",
                account_id="STEAM_NEW",
                name="Fresh",
            ),
        ]

        changes = apply_client_permissions(root, rules)

        self.assertEqual(changes, 2)

        updated = root.find(".//Client[@accountid='STEAM_123']")
        self.assertEqual(updated.get("permissions"), "All")
        self.assertEqual(updated.get("name"), "OldName")  # Not overwritten
        cmds = [c.get("name") for c in updated.findall("command")]
        self.assertEqual(cmds, ["new_cmd"])

        created = root.find(".//Client[@accountid='STEAM_NEW']")
        self.assertEqual(created.get("name"), "Fresh")

    def test_new_client_gets_rule_id_as_name(self):
        root = ET.Element("ClientPermissions")
        rules = [
            ClientPermissionRule(rule_id="MyAdmin", account_id="STEAM_NEW"),
        ]
        apply_client_permissions(root, rules)
        created = root.find(".//Client[@accountid='STEAM_NEW']")
        self.assertEqual(created.get("name"), "MyAdmin")

    def test_empty_rules(self):
        root = ET.Element("ClientPermissions")
        self.assertEqual(apply_client_permissions(root, []), 0)


class TestConfigureIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.server_settings = os.path.join(self.test_dir, "serversettings.xml")
        self.client_perms = os.path.join(self.test_dir, "clientpermissions.xml")
        self.marker_file = os.path.join(self.test_dir, ".client_perms_applied")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_configure_server_e2e(self):
        """Test full server settings flow: Env -> XML File"""
        env = {
            "S.ServerName": "Integration Test Server",
            "S.Physics.Gravity": "0.5"
        }
        
        # 1. Run configuration (creates new file)
        configure_server(env, self.server_settings)
        
        # 2. Verify file exists
        self.assertTrue(os.path.exists(self.server_settings))
        
        # 3. Verify content
        tree = ET.parse(self.server_settings)
        root = tree.getroot()
        self.assertEqual(root.tag, "serversettings")
        self.assertEqual(root.get("ServerName"), "Integration Test Server")
        self.assertEqual(root.find("Physics").get("Gravity"), "0.5")

    def test_configure_clients_marker_logic(self):
        """Test client permissions are applied only once unless forced."""
        env = {
            "C.Client.Owner.accountid": "STEAM_123",
            "C.Client.Owner.permissions": "All"
        }
        
        # 1. First run
        configure_clients(env, self.client_perms, self.marker_file)
        self.assertTrue(os.path.exists(self.client_perms))
        self.assertTrue(os.path.exists(self.marker_file))
        
        # Verify Owner exists
        tree = ET.parse(self.client_perms)
        root = tree.getroot()
        owner = root.find(".//Client[@accountid='STEAM_123']")
        self.assertIsNotNone(owner)
        self.assertEqual(owner.get("permissions"), "All")
        
        # 2. Change env and run again (Should be SKIPPED)
        env["C.Client.Owner.permissions"] = "None"
        configure_clients(env, self.client_perms, self.marker_file)
        
        # Verify NOT changed
        tree = ET.parse(self.client_perms)
        root = tree.getroot()
        owner = root.find(".//Client[@accountid='STEAM_123']")
        self.assertEqual(owner.get("permissions"), "All")
        
        # 3. Force override
        env["C.FORCE_OVERRIDES"] = "true"
        configure_clients(env, self.client_perms, self.marker_file)
        
        # Verify CHANGED
        tree = ET.parse(self.client_perms)
        root = tree.getroot()
        owner = root.find(".//Client[@accountid='STEAM_123']")
        self.assertEqual(owner.get("permissions"), "None")

    def test_save_xml_failure_cleanup(self):
        """Test that temp file is cleaned up if save fails (simulated)."""
        tree = ET.ElementTree(ET.Element("root"))
        target_path = os.path.join(self.test_dir, "target.xml")
        
        # Mock os.replace to fail
        with patch("os.replace", side_effect=OSError("Disk full")):
            with self.assertRaises(OSError):
                save_xml(tree, target_path)
        
        # Verify no temp files left in directory
        files = os.listdir(self.test_dir)
        # Should be empty or only contain unrelated files (none in this test setup)
        # tempfile.mkstemp creates files with random names, strict check:
        for f in files:
            self.assertFalse(f.startswith("tmp"), f"Found temp file: {f}")

    def test_sensitive_redaction_logging(self):
        """Verify password is not logged in plain text."""
        env = {"S.Password": "SuperSecret"}
        
        with self.assertLogs(level='INFO') as cm:
            configure_server(env, self.server_settings)
            
        # Check logs for redaction
        self.assertTrue(any("Set serversettings.Password = '***'" in output for output in cm.output))
        self.assertFalse(any("SuperSecret" in output for output in cm.output))


if __name__ == '__main__':
    unittest.main()
