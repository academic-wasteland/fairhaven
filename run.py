"""Run this town using an existing private relay identity; never commit its state."""
import argparse
from pathlib import Path
from wasteland.client import Client, save_config
from wasteland.fair_city import serve


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8396)
    parser.add_argument('--interval', type=int, default=300)
    parser.add_argument('--no-audit', action='store_true', help='Disable hourly service checks and liaison reports')
    args = parser.parse_args()
    if args.interval < 30:
        parser.error('--interval must be at least 30 seconds')
    client = Client(args.state)
    if client.name != 'fairhaven':
        parser.error('This deployment catalogue belongs to fairhaven. Fork and rename every publisher/access/record ID for another town.')
    client.config['fair_audit'] = not args.no_audit
    client.config['display'] = 'FAIRhaven'
    client.config['description'] = 'Provider-owned service and resource registry; register catalogues and discover research services.'
    client.config['fair_catalogue'] = str(Path(__file__).with_name('catalogue.jsonld').resolve())
    save_config(args.state, client.config)
    serve(args.state, port=args.port, interval=args.interval)


if __name__ == '__main__':
    main()
