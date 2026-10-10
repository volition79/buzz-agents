"""Verify official predecessor bytes and gate release completeness; client is offline.

--write is an explicit maintainer refresh. CI uses --check, never silently
blesses new hashes. API/manifest/download errors fail closed before publication.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'connect/provider-history.json'
BASE = 'https://github.com/volition79/buzz-agents/releases/download/'
FILE = 'buzz-backend-hostinger-https.exe'
TAG = re.compile(r'portal-candidate-[a-f0-9]{12}-[0-9]+-[0-9]+\Z')
DIGEST = re.compile(r'[a-f0-9]{64}\Z')


def fetch(url, limit):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'buzz-release-verifier'}), timeout=60) as r:
        raw = r.read(limit+1)
    if len(raw)>limit: raise ValueError('release_response_too_large')
    return raw


def validate_record(tag, record):
    if (not isinstance(tag,str) or not TAG.fullmatch(tag) or not isinstance(record,dict)
            or not isinstance(record.get('sha256'),str) or not DIGEST.fullmatch(record['sha256'])
            or type(record.get('size')) is not int or not 1 <= record['size'] <= 32*1024*1024):
        raise ValueError('invalid_provider_release_record')
    return {'tag':tag,'sha256':record['sha256'],'size':record['size']}


def verify_bytes(raw, record):
    if len(raw)!=record['size'] or hashlib.sha256(raw).hexdigest()!=record['sha256'] or not raw.startswith(b'MZ'):
        raise ValueError('provider_release_hash_mismatch')


def embedded_provider(installer, record):
    # Early releases shipped the backend only inside the Go installer embedding.
    # Accept a slice ONLY when its full manifest size and SHA256 match exactly.
    offset = installer.find(b'MZ')
    while offset >= 0:
        candidate = installer[offset:offset+record['size']]
        if len(candidate)==record['size'] and hashlib.sha256(candidate).hexdigest()==record['sha256']:
            return candidate
        offset = installer.find(b'MZ',offset+2)
    raise ValueError('embedded_provider_not_found')


def catalog(records):
    checked=[validate_record(r['tag'],r) for r in records]
    if not checked or len({r['tag'] for r in checked})!=len(checked):
        raise ValueError('empty_or_duplicate_release_history')
    return {'schema':1,'releases':sorted(checked,key=lambda r:r['tag'])}


def discover(download_dir):
    releases=[]
    for page in range(1,101):
        batch=json.loads(fetch('https://api.github.com/repos/volition79/buzz-agents/releases?per_page=100&page='+str(page),4*1024*1024))
        if not isinstance(batch,list):raise ValueError('invalid_release_list')
        releases.extend(batch)
        if len(batch)<100:break
    else:raise ValueError('release_history_pagination_limit')
    records=[]; verified={}
    download_dir.mkdir(parents=True,exist_ok=True)
    for release in releases:
        tag=release['tag_name']
        if release.get('draft') or not TAG.fullmatch(tag):continue
        manifest=json.loads(fetch(BASE+tag+'/manifest.json',1024*1024))
        record=validate_record(tag,manifest['files'][FILE]);records.append(record)
        path=download_dir/(record['sha256']+'.exe')
        if record['sha256'] in verified:
            if verified[record['sha256']]!=record['size']:raise ValueError('inconsistent_release_size')
            continue
        if path.is_file():raw=path.read_bytes()
        elif FILE in {a['name'] for a in release['assets']}:
            raw=fetch(BASE+tag+'/'+FILE,32*1024*1024)
        else:
            installer=fetch(BASE+tag+'/Buzz-VPS-Connect.exe',32*1024*1024)
            verify_bytes(installer,validate_record(tag,manifest['files']['Buzz-VPS-Connect.exe']))
            raw=embedded_provider(installer,record)
        verify_bytes(raw,record)
        if not path.exists():path.write_bytes(raw)
        verified[record['sha256']]=record['size']
    return catalog(records)


def check_catalog(saved, current):
    saved=catalog(saved['releases'])
    for r in current['releases']:
        if r not in saved['releases']:raise ValueError('provider_history_incomplete_run_explicit_write_and_review')


def main():
    parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write',action='store_true');mode.add_argument('--check',action='store_true')
    parser.add_argument('--download-dir',type=Path,required=True);args=parser.parse_args()
    current=discover(args.download_dir)
    if args.write:
        # Never silently drop previously reviewed hashes if a release disappears.
        old=json.loads(CATALOG.read_text()) if CATALOG.exists() else {'releases':[]}
        merged={r['tag']:r for r in old['releases']}
        for r in current['releases']:
            if r['tag'] in merged and merged[r['tag']]!=r:raise ValueError('published_release_changed')
            merged[r['tag']]=r
        current=catalog(list(merged.values()))
        CATALOG.write_text(json.dumps(current,indent=2)+'\n')
    else:
        check_catalog(json.loads(CATALOG.read_text()),current)
    print(json.dumps({'public_releases':len(current['releases']),'unique_providers':len({r['sha256'] for r in current['releases']}),'status':'verified'}))

if __name__=='__main__':main()
