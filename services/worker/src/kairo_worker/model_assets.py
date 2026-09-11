"""Explicit inventory of locally provisioned model bytes; never downloads or updates weights."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def inventory(root: Path) -> dict[str, str]:
    result = {}
    root = root.resolve()
    for path in sorted(root.rglob('*')):
        if path.name == 'manifest.json' and path.parent == root:
            continue
        if not path.resolve().is_relative_to(root):
            raise ValueError('Model asset link escapes its bundle')
        if path.is_file():
            with path.open('rb') as source:
                result[path.relative_to(root).as_posix()] = hashlib.file_digest(source, 'sha256').hexdigest()
    return result


def verify_manifest(path: Path) -> None:
    manifest = json.loads(path.read_text())
    if manifest.get('version') != 1 or not manifest.get('sources') or not manifest.get('files'):
        raise ValueError('Model bundle requires sources and a nonempty SHA-256 inventory')
    if manifest['files'] != inventory(path.parent):
        raise ValueError('Model bundle is incomplete or changed; explicit upgrade required')


def verify_production_assets() -> None:
    value = os.environ.get('KAIRO_MODEL_ASSETS_MANIFEST', '')
    if not value:
        raise RuntimeError('Production requires a verified local model bundle')
    verify_manifest(Path(value))
    if os.environ.get('HF_HUB_OFFLINE') != '1' or os.environ.get('TRANSFORMERS_OFFLINE') != '1':
        raise RuntimeError('Production model downloads must be disabled')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['record', 'verify'])
    parser.add_argument('directory', type=Path)
    parser.add_argument('--source', action='append', help='Engine, model ID, upstream revision and license reviewed by operator')
    args = parser.parse_args()
    path = args.directory / 'manifest.json'
    if args.action == 'record':
        if not args.source or path.exists():
            raise SystemExit('Provide sources in a new bundle directory; existing manifests cannot be overwritten')
        files = inventory(args.directory)
        if not files:
            raise SystemExit('Cannot record an empty model bundle')
        with path.open('x') as dest:
            json.dump({'version': 1, 'sources': args.source, 'files': files}, dest, indent=2)
            dest.flush(); os.fsync(dest.fileno())
    verify_manifest(path)
    print('Model bundle hashes verified; engine compatibility is a separate D04 proof')


if __name__ == '__main__':
    main()
