"""Exercise the documented commands and launcher against an isolated real relay."""
import json
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

from wasteland.client import Client, join
from wasteland.fair import digest
from wasteland.hub import Store, handler

ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        store = Store(self.root / 'relay.sqlite')
        self.addCleanup(store.db.close)
        invite = secrets.token_urlsafe(32)
        relay = ThreadingHTTPServer(('127.0.0.1', 0), handler(store, invite, 'http://127.0.0.1'))
        self.addCleanup(relay.server_close)
        thread = threading.Thread(target=relay.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(relay.shutdown)
        base = f'http://127.0.0.1:{relay.server_port}'
        for town in ('fairhaven', 'researchlab'):
            join(self.root / town, base, town, invite)
        self.processes = []
        self.addCleanup(self.stop_processes)

    def stop_processes(self):
        for process in reversed(self.processes):
            self.stop(process)

    @staticmethod
    def stop(process):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def launch(self, args, label):
        path = self.root / f'{label}.log'
        with path.open('w') as log:
            process = subprocess.Popen([sys.executable, *args], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        self.processes.append(process)
        return process, path

    def start_registry(self, label):
        process, log = self.launch(['run.py', '--state', str(self.root / 'fairhaven'), '--port', '0', '--interval', '300'], label)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            output = log.read_text()
            match = re.search(r'FAIR city: (http://127.0.0.1:\d+)/', output)
            if match:
                self.base = match[1]
                return process
            self.assertIsNone(process.poll(), output)
            time.sleep(.1)
        self.fail('Registry startup timed out: ' + log.read_text())

    def cli(self, *args, success=True):
        result = subprocess.run([sys.executable, '-m', 'wasteland', '--state', str(self.root / 'researchlab'), *args], cwd=ROOT, capture_output=True, text=True, timeout=130)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def get(self, path):
        with urlopen(self.base + path, timeout=5) as response:
            return json.load(response)

    def register(self, doc):
        source = self.root / 'provider.jsonld'
        source.write_text(json.dumps(doc))
        self.cli('fair-publish', str(source))
        output = self.cli('fair-register', '--to', 'fairhaven').stdout
        body = json.loads(output[output.index('{'):])
        self.assertTrue(body['ok'], body)
        receipt = body['registration']
        self.assertEqual(receipt['revision'], digest(doc))
        self.assertEqual(receipt['count'], len(doc['@graph']))
        self.assertEqual(receipt['owner'], 'researchlab')
        return receipt

    def test_cli_registration_update_withdrawal_and_restart(self):
        missing = self.cli('fair-register', success=False)
        self.assertIn('fair-publish', missing.stdout + missing.stderr)
        doc = json.loads((ROOT / 'catalogue.jsonld').read_text())
        doc['@graph'] = doc['@graph'][:2]
        for record in doc['@graph']:
            record['@id'] = record['@id'].replace(':fairhaven:', ':researchlab:')
            record['publisher'] = 'urn:wasteland:town:researchlab'
            record['access']['town'] = 'researchlab'
        # Publish before starting the worker, as instructed in the README.
        source = self.root / 'provider.jsonld'
        source.write_text(json.dumps(doc))
        self.cli('fair-publish', str(source))
        self.launch(['-m', 'wasteland', '--state', str(self.root / 'researchlab'), 'work'], 'provider')
        registry = self.start_registry('registry')
        self.register(doc)
        self.assertTrue(self.get('/healthz')['ok'])
        self.assertEqual(len(self.get('/api/search?town=fairhaven')['results']), 4)
        self.assertEqual(len(self.get('/api/search?town=researchlab')['results']), 2)
        first, removed = [r['@id'] for r in doc['@graph']]
        doc['@graph'] = doc['@graph'][:1]
        doc['@graph'][0]['version'] = '2.0.0'
        receipt = self.register(doc)
        record_url = '/api/record?' + urlencode({'id': first})
        record = self.get(record_url)
        self.assertEqual(record['record']['version'], '2.0.0')
        self.assertEqual(len(record['revisions']), 2)
        removed_url = '/api/record?' + urlencode({'id': removed})
        self.assertEqual(self.get(removed_url)['publication'], 'withdrawn')
        export = self.get('/catalogue.jsonld')
        self.assertNotIn(removed, [r['@id'] for r in export['@graph']])
        for town in ('fairhaven', 'researchlab'):
            self.assertNotIn(Client(self.root / town).config['token'], json.dumps(export))
        with self.assertRaises(HTTPError) as error:
            self.get('/api/record?id=unknown')
        self.assertEqual(error.exception.code, 404)
        error.exception.close()
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base + '/api/search', data=b'{}', timeout=5)
        self.assertEqual(error.exception.code, 501)
        error.exception.close()
        self.stop(registry)
        self.start_registry('restarted')
        self.assertEqual(self.get(record_url)['revisions'], record['revisions'])
        self.assertEqual(self.get(removed_url)['publication'], 'withdrawn')
        provider = Client(self.root / 'researchlab')
        mid = provider.ask('fairhaven', operation='fair-registration')
        reply = provider.wait(mid, 20)[0]
        self.assertEqual(reply['body']['registration'], receipt)
        # Empty publication is a deliberate withdrawal of all this provider's records.
        doc['@graph'] = []
        self.register(doc)
        self.assertTrue(all(r['publication'] == 'withdrawn' for r in self.get('/api/search?town=researchlab')['results']))
        self.assertEqual(len(self.get('/catalogue.jsonld')['@graph']), 4)
