"""Private STC operator CLI. Never distribute this tool or server data to buyers."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from .core import Authority,create_secrets


def https_url(url):
    parsed=urlsplit(url)
    if (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or any(c.isspace() for c in url)):
        raise ValueError('A public HTTPS licensing URL is required')
    parsed.port
    return url.rstrip('/')


def provision(authority,client_root,url):
    provision_public({'server_url':url,'public_key':authority.public_key()},client_root)


def provision_public(data,client_root):
    url=https_url(data['server_url'])
    key=data['public_key']
    if not isinstance(key,dict) or int(key['n'],16).bit_length()!=3072 or key['e']!=65537 or len(key['key_id'])!=24:
        raise ValueError('Invalid public licensing configuration')
    package=Path(client_root)/'stc_statistics'
    if not (package/'app.py').is_file():
        raise ValueError('Choose the STC Statistics source directory')
    (package/'license_trust.py').write_text(
        '"""Public verification key; contains no server secrets."""\nPUBLIC_KEY = '+repr(key)+'\n',encoding='utf-8')
    (package/'license_config.json').write_text(json.dumps({'server_url':url},indent=2)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',default='licensing_data')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init')
    issue=sub.add_parser('issue')
    issue.add_argument('--buyer',required=True,help='Internal purchase/reference number')
    issue.add_argument('--days',type=int,help='Optional expiry; omitted means no expiry')
    sub.add_parser('list')
    for operation in ('revoke','transfer'):
        child=sub.add_parser(operation)
        child.add_argument('license_id')
    client=sub.add_parser('configure-client')
    client.add_argument('--root',required=True)
    client.add_argument('--url',help='Your deployed HTTPS licensing API origin (with local server data)')
    client.add_argument('--public-config',help='Exported public configuration; needs no private server data')
    export=sub.add_parser('export-public')
    export.add_argument('--url',required=True)
    args=parser.parse_args()
    if args.command=='configure-client' and args.public_config:
        provision_public(json.loads(Path(args.public_config).read_text(encoding='utf-8-sig')),args.root)
        print('Client configured using public material only. No private keys needed or copied.')
        return
    if args.command=='configure-client' and not args.url:
        parser.error('configure-client needs --public-config or --url')
    directory=Path(args.data)
    if args.command=='init':
        create_secrets(directory/'private')
    authority=Authority(directory/'licenses.sqlite3',directory/'private')
    if args.command=='init':
        print('Licensing database and private signing material initialized. Back up the entire data directory securely.')
    elif args.command=='issue':
        identifier,code=authority.issue(args.buyer,args.days)
        print(json.dumps({'license_id':identifier,'code':code}))
    elif args.command=='list':
        with authority.connect() as db:
            rows=db.execute('SELECT id,buyer_ref,revoked,created,activated,expires,device_id IS NOT NULL AS assigned FROM licenses ORDER BY created DESC').fetchall()
        print(json.dumps([dict(row) for row in rows],indent=2))
    elif args.command=='revoke':
        authority.revoke(args.license_id)
        print('License revoked. Takes effect on the next application launch.')
    elif args.command=='transfer':
        print(json.dumps({'license_id':args.license_id,'replacement_code':authority.transfer(args.license_id)}))
    elif args.command=='configure-client':
        provision(authority,args.root,args.url)
        print('Client HTTPS endpoint and public verification key configured. No private keys copied.')
    elif args.command=='export-public':
        print(json.dumps({'server_url':https_url(args.url),'public_key':authority.public_key()},indent=2))


if __name__=='__main__':
    main()
