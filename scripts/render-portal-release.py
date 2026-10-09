"""Render an install Compose only from three exact reviewed image digests."""
import argparse
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


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for role in ('runtime','broker','portal'):parser.add_argument('--'+role,required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    args.output.write_text(render({k:getattr(args,k) for k in ('runtime','broker','portal')}))
