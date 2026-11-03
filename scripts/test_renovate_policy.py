import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RenovatePolicyTests(unittest.TestCase):
    def test_comment_free_source_pins_are_extracted_together(self):
        config = json.loads((ROOT / 'renovate.json').read_text())
        expected = {'restic/restic': ('RESTIC', 'backup'), 'caddyserver/caddy': ('CADDY', 'frontend')}
        managers = {item.get('packageNameTemplate'): item for item in config['customManagers']}
        self.assertEqual(set(managers), set(expected))
        for package, (name, filename) in expected.items():
            manager = managers[package]
            self.assertEqual(manager['datasourceTemplate'], 'github-tags')
            pattern = manager['matchStrings'][0].replace('(?<', '(?P<')
            fixture = 'ARG ' + name + '_VERSION=v1.2.3\nARG ' + name + '_COMMIT=' + 'a' * 40 + '\n'
            match = re.search(pattern, fixture)
            self.assertIsNotNone(match)
            self.assertEqual(match.group('currentValue'), 'v1.2.3')
            self.assertEqual(match.group('currentDigest'), 'a' * 40)
            self.assertIsNotNone(re.search(pattern, (ROOT / ('docker/Dockerfile.' + filename)).read_text()))

    def test_bot_policy_keeps_major_review_and_manual_providers_without_platform_automerge(self):
        config = json.loads((ROOT / 'renovate.json').read_text())
        self.assertTrue(config['enabled'])
        self.assertFalse(config['platformAutomerge'])
        self.assertEqual(config['automergeType'], 'pr')
        rules = config['packageRules']
        self.assertTrue(any(rule.get('matchManagers') == ['terraform'] and rule.get('enabled') is False for rule in rules))
        self.assertTrue(any(rule.get('matchUpdateTypes') == ['major'] and rule.get('dependencyDashboardApproval') is True and rule.get('automerge') is False for rule in rules))
        self.assertTrue(any(rule.get('matchUpdateTypes') == ['minor', 'patch'] and rule.get('automerge') is True for rule in rules))


if __name__ == '__main__':
    unittest.main()
