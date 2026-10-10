"""Render an install Compose only from three exact reviewed image digests."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def render(images):
    text=(ROOT/'compose.portal.yaml').read_text()
    for role in ('runtime','broker','portal'):
        image=images[role]
        if not re.fullmatch(r'[a-z0-9][a-z0-9._/-]+@sha256:[a-f0-9]{64}',image):
            raise ValueError('immutable_image_digest_required_'+role)
        key='BUZZ_'+role.upper()+'_IMAGE'
        text=re.sub(r'\$\{'+key+r':\?[^}]+\}',lambda _:image,text)
    return text


def atomic_text(path, text):
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def check_files(directory, files):
    for name, record in files.items():
        if (Path(name).name != name or '\n' in name or '\r' in name
                or name in (".", "..", "manifest.json", "SHA256SUMS")):
            raise ValueError("invalid_manifest_filename")
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("manifest_file_missing")
        raw = path.read_bytes()
        if record != {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}:
            raise ValueError("manifest_hash_mismatch")


def checksum_text(files):
    return "".join(record["sha256"] + "  " + name + "\n" for name, record in sorted(files.items()))


def write_release(images, output):
    # Verify prior artifacts before adding the final Compose; never bless a
    # corrupted executable merely by regenerating all hashes from current bytes.
    manifest_path = output.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    prior = {k: v for k, v in manifest["files"].items() if k != output.name}
    check_files(output.parent, prior)
    text = render(images)
    raw = text.encode("utf8")
    atomic_text(output, text)
    manifest["files"] = {**prior, output.name: {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}}
    atomic_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    atomic_text(output.parent / "SHA256SUMS", checksum_text(manifest["files"]))
    verify_release(output)


def verify_release(output):
    manifest = json.loads((output.parent / "manifest.json").read_text())
    if output.name not in manifest["files"]:
        raise ValueError("release_compose_not_in_manifest")
    check_files(output.parent, manifest["files"])
    if (output.parent / "SHA256SUMS").read_text() != checksum_text(manifest["files"]):
        raise ValueError("checksum_list_mismatch")


def release_assets(output):
    verify_release(output)
    manifest = json.loads((output.parent / "manifest.json").read_text())
    return [output.parent / name for name in sorted(manifest['files'])] + [
        output.parent / 'manifest.json', output.parent / 'SHA256SUMS']


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for role in ('runtime','broker','portal'):parser.add_argument('--'+role)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--verify',action='store_true')
    parser.add_argument('--list-assets',action='store_true')
    args=parser.parse_args()
    if args.list_assets:
        print('\n'.join(str(path) for path in release_assets(args.output)))
    elif args.verify:
        verify_release(args.output)
    else:
        if not all(getattr(args, role) for role in ('runtime','broker','portal')):
            parser.error('all three image digests are required')
        write_release({k:getattr(args,k) for k in ('runtime','broker','portal')}, args.output)
