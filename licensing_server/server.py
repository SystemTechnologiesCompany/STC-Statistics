"""Private HTTP listener: deploy behind an HTTPS reverse proxy; no remote admin API."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
from .core import Authority,Denied


def create_server(authority,host='127.0.0.1',port=8765,trusted_proxies=()):
    trusted=[ipaddress.ip_network(value) for value in trusted_proxies]
    class Handler(BaseHTTPRequestHandler):
        server_version='STC-Licensing'
        sys_version=''
        def log_message(self,*args):
            pass  # Codes, tokens, buyer references and request bodies are never logged.
        def send_json(self,status,data):
            raw=json.dumps(data,separators=(',',':')).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            self.wfile.write(raw)
        def do_GET(self):
            self.send_json(200,{'service':'STC licensing','status':'ok'}) if self.path=='/health' else self.send_json(404,{'code':'STC-L104'})
        def do_POST(self):
            self.connection.settimeout(15)
            if self.path not in ('/v1/activate','/v1/validate'):
                self.send_json(404,{'code':'STC-L104'})
                return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=4096 or self.headers.get_content_type()!='application/json' or self.headers.get('Transfer-Encoding'):
                    raise Denied('STC-L101',400)
                raw=self.rfile.read(size)
                if len(raw)!=size:
                    raise Denied('STC-L101',400)
                ip=self.client_address[0]
                if any(ipaddress.ip_address(ip) in network for network in trusted):
                    forwarded=self.headers.get('X-Forwarded-For','').split(',')[-1].strip()
                    if forwarded:
                        ip=str(ipaddress.ip_address(forwarded))
                data=authority.access(self.path.rsplit('/',1)[1],json.loads(raw),ip)
                self.send_json(200,data)
            except Denied as exc:
                self.send_json(exc.status,{'code':exc.code})
            except (ValueError,UnicodeError):
                self.send_json(400,{'code':'STC-L101'})
            except Exception:
                self.send_json(503,{'code':'STC-L104'})
    return ThreadingHTTPServer((host,port),Handler)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',default=os.environ.get('STC_LICENSE_DATA','licensing_data'))
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--trusted-proxy',action='append',default=[])
    args=parser.parse_args()
    directory=Path(args.data)
    authority=Authority(directory/'licenses.sqlite3',directory/'private')
    create_server(authority,args.host,args.port,args.trusted_proxy).serve_forever()
