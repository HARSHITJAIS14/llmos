import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from pipeline import Client, read_key_file

class ClientTests(unittest.TestCase):
    def test_gemini_request(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'GEMINI_API_KEY': 'test-secret'}, clear=True):
            out = Path(tmp)
            client = Client('https://generativelanguage.googleapis.com/v1beta/openai', 'gemini-3.8-flash', out)
            response = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{"label":"screen"}'}}]}
            with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(response).encode())) as request:
                self.assertEqual(client.ask('inspect', [Image.new('RGB', (8, 8))]), {'label': 'screen'})
                req = request.call_args.args[0]
                body = json.loads(req.data)
                self.assertEqual(req.get_header('Authorization'), 'Bearer test-secret')
                self.assertEqual(body['model'], 'gemini-3.8-flash')
                self.assertEqual(body['reasoning_effort'], 'low')
                self.assertEqual(body['response_format'], {'type': 'json_object'})
                self.assertTrue(body['messages'][0]['content'][1]['image_url']['url'].startswith('data:image/png;base64,'))
            self.assertNotIn('test-secret', (out / '001.json').read_text())

    def test_google_key_not_sent_to_custom_endpoint(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-secret'}, clear=True):
            self.assertIsNone(Client('http://localhost:8000/v1', 'local', Path('.')).api_key)

    def test_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'Set GEMINI_API_KEY'):
                Client('https://generativelanguage.googleapis.com/v1beta/openai', 'gemini-3.8-flash', Path('.'))

    def test_dotenv_not_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.env'
            path.write_text('OTHER_KEY=ignored\nexport GEMINI_API_KEY="$(never-execute)"\n')
            self.assertEqual(read_key_file(path, ('GEMINI_API_KEY',)), '$(never-execute)')

    def test_malformed_json_retry_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = Client('http://localhost:8000/v1', 'test', Path(tmp))
            raw = {'choices': [{'finish_reason': 'stop', 'message': {'content': 'invalid'}}]}
            responses = [io.BytesIO(json.dumps(raw).encode()) for _ in range(2)]
            with patch('urllib.request.urlopen', side_effect=responses) as request:
                with self.assertRaises(ValueError):
                    client.ask('inspect', [])
                self.assertEqual(request.call_count, 2)
            self.assertEqual(len(list(Path(tmp).glob('*.json'))), 2)
