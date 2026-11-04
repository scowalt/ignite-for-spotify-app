from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseWorkflowTests(unittest.TestCase):
    def test_only_protected_publisher_can_sign_and_promote_after_all_image_pushes(self):
        ci = (ROOT / '.github/workflows/ci.yml').read_text()
        publish = ci.split('  publish:\n', 1)[1].split('\n  backend:', 1)[0]
        deploy = (ROOT / '.github/workflows/deploy.yml').read_text()
        self.assertIn('      id-token: write', publish)
        self.assertEqual(ci.count('id-token: write'), 1)
        self.assertEqual(deploy.count('id-token: write'), 1)
        self.assertIn('    environment: production', deploy)
        names = ['Verify final image notices and security before any push',
                 'Verify current release head', 'Publish verified images',
                 'Create coherent release record', 'Sign and verify release record',
                 'Promote signed release pointer']
        positions = [deploy.index('- name: ' + name) for name in names]
        self.assertEqual(positions, sorted(positions))
        signing = deploy.split('      - name: Sign and verify release record\n', 1)[1].split('\n      - name:', 1)[0]
        for flag in ['--certificate-identity', '--certificate-oidc-issuer', '--certificate-github-workflow-sha', '--certificate-github-workflow-repository', '--certificate-github-workflow-ref']:
            self.assertIn(flag, signing)
        for bypass in ['--insecure-ignore', '--check-claims=false', '--allow-insecure', 'continue-on-error']:
            self.assertNotIn(bypass, signing)
        promotion = deploy.split('      - name: Promote signed release pointer\n', 1)[1].split('\n      - name:', 1)[0]
        self.assertIn('commits/main --jq .sha', promotion)
        self.assertIn('RELEASE_RECORD_DIGEST', promotion)

    def test_record_packaging_uses_one_platform_without_buildkit_attestations(self):
        workflow = (ROOT / '.github/workflows/deploy.yml').read_text()
        record = workflow.split('      - name: Create coherent release record\n', 1)[1].split('\n      - name:', 1)[0]
        for option in ['--migration-protocol', 'docker buildx build', '--load', '--platform linux/amd64', '--provenance=false', '--sbom=false']:
            self.assertIn(option, record)


if __name__ == '__main__':
    unittest.main()
