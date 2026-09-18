"""Read-only smoke check of the public registry and its relay advertisement."""
import argparse
import json
from urllib.parse import urlencode
from urllib.request import urlopen

from wasteland.fair import document, validate


def check(registry, relay):
    def get(url):
        with urlopen(url, timeout=20) as response:
            return json.load(response)
    registry = registry.rstrip('/')
    if get(registry + '/healthz').get('ok') is not True:
        raise ValueError('Registry health check failed')
    records = get(registry + '/catalogue.jsonld')['@graph']
    owners = {}
    for record in records:
        owner = record['publisher'].removeprefix('urn:wasteland:town:')
        owners.setdefault(owner, []).append(record)
    for owner, items in owners.items():
        validate(document(items), owner)
    expected = {'fair-register', 'fair-registration', 'fair-search', 'fair-record', 'fair-catalogue'}
    towns = get(relay.rstrip('/') + '/.well-known/wasteland.json')['towns']
    town = next(t for t in towns if t['name'] == 'fairhaven')
    if not expected.issubset(town['capabilities']):
        raise ValueError('FAIRhaven is missing advertised operations')
    own = get(registry + '/api/search?town=fairhaven')['results']
    if len(own) != 4 or any(r['publication'] != 'listed' for r in own):
        raise ValueError('FAIRhaven self-descriptions are missing')
    for row in own:
        identifier = row['record']['@id']
        detail = get(registry + '/api/record?' + urlencode({'id': identifier}))
        if detail['record'] != row['record'] or not detail['revisions']:
            raise ValueError('Record lookup/history disagrees with search')
    return {'ok': True, 'listed_records': len(records), 'towns': sorted(owners), 'advertised_operations': sorted(expected)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', default='https://leechuck.de/wasteland-fair')
    parser.add_argument('--relay', default='https://leechuck.de/wasteland')
    args = parser.parse_args()
    print(json.dumps(check(args.registry, args.relay), indent=2))
