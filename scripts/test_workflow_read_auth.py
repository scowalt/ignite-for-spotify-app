import base64
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from release_record import ReleaseRejected
from release_transport import public_workflow


class Response(io.BytesIO):
    def __init__(self, scopes='read:packages'):
        super().__init__(b'{"id":123,"status":"completed","conclusion":"success"}')
        self.headers = {'X-OAuth-Scopes': scopes}


class WorkflowReadAuthTests(unittest.TestCase):
    def test_public_workflow_uses_existing_read_only_registry_auth_without_new_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            content = json.dumps({'auths': {'ghcr.io': {'auth': base64.b64encode(b'fixture-user:fixture-read-only').decode()}}})
            path.write_text(content)
            path.chmod(0o600)
            captured = []
            class Transport:
                def open(self, request, timeout):
                    captured.append(request)
                    self_response = Response()
                    return self_response
            with patch.dict(os.environ, {'DOCKER_CONFIG': directory}), patch('urllib.request.build_opener', return_value=Transport()):
                value = public_workflow(123)
            self.assertEqual(value['id'], 123)
            self.assertEqual(captured[0].full_url, 'https://api.github.com/repos/scowalt/ignite-for-spotify-app/actions/runs/123')
            self.assertEqual(captured[0].get_header('Authorization'), 'Bearer fixture-read-only')
            self.assertEqual(path.read_text(), content)

    def test_missing_or_broader_credentials_are_not_silently_substituted(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'DOCKER_CONFIG': directory}), patch('urllib.request.build_opener', side_effect=AssertionError('No request without the existing credential')), self.assertRaises(ReleaseRejected):
                public_workflow(123)
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps({'auths': {'ghcr.io': {'auth': base64.b64encode(b'fixture-user:fixture-read-only').decode()}}}))
            path.chmod(0o600)
            class Transport:
                def open(self, request, timeout):
                    return Response('repo,read:packages')
            with patch.dict(os.environ, {'DOCKER_CONFIG': directory}), patch('urllib.request.build_opener', return_value=Transport()), self.assertRaises(ReleaseRejected):
                public_workflow(123)


if __name__ == '__main__':
    unittest.main()
