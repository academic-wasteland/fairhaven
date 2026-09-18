import json
import unittest
from pathlib import Path
from wasteland.fair import validate, assess

class CatalogueTests(unittest.TestCase):
    def test_self_descriptions(self):
        doc = json.loads((Path(__file__).resolve().parents[1]/'catalogue.jsonld').read_text())
        records = validate(doc, 'fairhaven')
        self.assertEqual(len(records), 4)
        self.assertEqual({r['kind'] for r in records}, {'service','dataset','resource'})
        for r in records:
            self.assertTrue(all(c['status']=='present' for c in assess(r)['checks']))
