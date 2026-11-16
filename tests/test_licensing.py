import base64
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib import request,error

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtCore import QSettings
from licensing_server.core import Authority,Denied,create_secrets,canonical
from licensing_server.server import create_server
from licensing_server.manage import provision,provision_public
from stc_statistics.licensing import LicenseClient,CredentialStore,LicenseError,validate_server_url,require_configured_release
from stc_statistics import license_windows
from stc_statistics.activation import ActivationDialog,LicenseWorker


class LicensingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys=tempfile.TemporaryDirectory()
        create_secrets(Path(cls.keys.name)/'private')

    @classmethod
    def tearDownClass(cls):
        cls.keys.cleanup()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.authority=Authority(self.root/'licenses.sqlite3',Path(self.keys.name)/'private')
        self.identifier,self.code=self.authority.issue('university-purchase-123')
        self.device='a'*64

    def activate(self,device=None,code=None):
        return self.authority.access('activate',{'device_id':device or self.device,
             'nonce':secrets.token_hex(24),'code':code or self.code},'127.0.0.1')

    def validate(self,token,device=None):
        return self.authority.access('validate',{'device_id':device or self.device,
             'nonce':secrets.token_hex(24),'token':token},'127.0.0.1')

    def assertDenied(self,code,call):
        with self.assertRaises((Denied,LicenseError)) as caught:
            call()
        self.assertEqual(caught.exception.code,code)

    def test_single_seat_blocks_second_device_and_reactivation_rotates_token(self):
        first=self.activate()['payload']['token']
        self.assertEqual(self.validate(first)['payload']['license_id'],self.identifier)
        self.assertDenied('STC-L102',lambda:self.activate(device='b'*64))
        self.assertDenied('STC-L102',lambda:self.validate(first,device='b'*64))
        second=self.activate()['payload']['token']
        self.assertNotEqual(first,second)
        self.assertDenied('STC-L101',lambda:self.validate(first))
        self.validate(second)

    def test_atomic_concurrent_first_activation(self):
        def attempt(device):
            try:
                self.activate(device=device)
                return 'accepted'
            except Denied as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(attempt,['a'*64,'b'*64]))
        self.assertCountEqual(outcomes,['accepted','STC-L102'])

    def test_revoke_and_transfer_retire_old_code_and_token(self):
        token=self.activate()['payload']['token']
        self.authority.revoke(self.identifier)
        self.assertDenied('STC-L103',lambda:self.validate(token))
        replacement=self.authority.transfer(self.identifier)
        self.assertDenied('STC-L101',lambda:self.activate(code=self.code))
        self.assertDenied('STC-L101',lambda:self.validate(token))
        self.activate(device='b'*64,code=replacement)

    def test_expiry_enforced(self):
        token=self.activate()['payload']['token']
        with self.authority.connect() as db:
            db.execute('UPDATE licenses SET expires=?',(int(time.time())-1,))
        self.assertDenied('STC-L103',lambda:self.validate(token))

    def test_codes_and_tokens_never_stored_in_plaintext(self):
        token=self.activate()['payload']['token']
        with self.authority.connect() as db:
            row=dict(db.execute('SELECT * FROM licenses').fetchone())
        self.assertNotIn(self.code,json.dumps(row))
        self.assertNotIn(token,json.dumps(row))
        self.assertEqual(len(row['code_hash']),64)

    def test_rate_limit_and_malformed_requests(self):
        for _ in range(5):
            self.assertDenied('STC-L101',lambda:self.activate(code='wrong'))
        self.assertDenied('STC-L106',lambda:self.activate(code='wrong'))
        for body in ([],{}, {'device_id':'bad','nonce':'bad'}):
            self.assertDenied('STC-L101',lambda:self.authority.access('activate',body,'127.0.0.1'))
        self.assertDenied('STC-L101',lambda:self.authority.access('admin',{},'127.0.0.1'))

    def client(self,identity=None):
        return LicenseClient('https://license.example.test',self.authority.public_key(),
                             store=CredentialStore(self.root/'activation.bin'),identity=identity or self.device)

    def test_dpapi_storage_and_device_fingerprint(self):
        raw=b'private activation credential'
        encrypted=license_windows.protect(raw)
        self.assertNotIn(raw,encrypted)
        self.assertEqual(license_windows.protect(encrypted,decrypt=True),raw)
        with self.assertRaises(OSError):
            license_windows.protect(b'copied invalid data',decrypt=True)
        self.assertRegex(license_windows.device_id(),r'^[0-9a-f]{64}$')
        self.assertEqual(license_windows.device_id(),license_windows.device_id())

    def test_signature_nonce_device_expiry_and_payload_tampering(self):
        client=self.client()
        nonce=secrets.token_hex(24)
        payload=self.authority.access('activate',{'code':self.code,'device_id':self.device,'nonce':nonce},'127.0.0.1')['payload']
        self.assertEqual(client.verify(self.authority.sign(payload),nonce),payload)
        bad=dict(payload,active=False)
        envelope=self.authority.sign(payload)
        envelope['payload']=bad
        self.assertDenied('STC-L108',lambda:client.verify(envelope,nonce))
        for change in ({'nonce':secrets.token_hex(24)},{'device_id':'b'*64},
                       {'expires_at':time.time()-1},{'issued_at':time.time()+10000},
                       {'expires_at':time.time()+10000},{'active':False}):
            envelope=self.authority.sign(dict(payload,**change))
            self.assertDenied('STC-L108',lambda:client.verify(envelope,nonce))
        for envelope in ({}, {'payload':payload,'signature':'invalid','key_id':'bad'}):
            self.assertDenied('STC-L108',lambda:client.verify(envelope,nonce))

    def test_wrong_public_key_is_rejected(self):
        nonce=secrets.token_hex(24)
        envelope=self.authority.access('activate',{'code':self.code,'device_id':self.device,'nonce':nonce},'127.0.0.1')
        key=dict(self.authority.public_key())
        # Different modulus, same key identifier: signature math must still fail.
        key['n']=format(int(key['n'],16)^2,'x')
        client=self.client()
        client.public_key=key
        self.assertDenied('STC-L108',lambda:client.verify(envelope,nonce))

    def test_missing_corrupt_and_copied_credentials_fail_closed(self):
        client=self.client()
        self.assertDenied('STC-L100',client.check)
        client.store.path.write_bytes(b'fake activation file')
        self.assertDenied('STC-L105',client.check)
        client.store.save({'server_url':client.url,'device_id':self.device,'token':'x'*43,'license_id':self.identifier})
        copied=self.client(identity='b'*64)
        self.assertDenied('STC-L105',copied.check)
        client.store.save(['malformed credential'])
        self.assertDenied('STC-L105',client.check)

    def test_https_required_and_unconfigured_client_fails_closed(self):
        for url in ('','http://example.test','https://u:p@example.test','https://example.test?token=x','https://example.test#x','https://example.test:bad'):
            self.assertDenied('STC-L104',lambda:validate_server_url(url))
        with patch('stc_statistics.licensing.load_config',return_value=''),patch('stc_statistics.licensing.PUBLIC_KEY',None):
            self.assertDenied('STC-L104',LicenseClient)

    def test_end_to_end_http_activation_validation_and_no_admin_api(self):
        server=create_server(self.authority,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            url='http://127.0.0.1:'+str(server.server_address[1])
            client=LicenseClient(url,self.authority.public_key(),CredentialStore(self.root/'activation.bin'),
                                 identity=self.device,allow_local_http=True)
            client.activate(self.code)
            self.assertEqual(client.check()['license_id'],self.identifier)
            saved=client.store.load()
            self.assertNotIn('code',saved)
            self.assertNotIn(saved['token'].encode(),client.store.path.read_bytes())
            other=LicenseClient(url,self.authority.public_key(),CredentialStore(self.root/'other.bin'),
                                identity='b'*64,allow_local_http=True)
            self.assertDenied('STC-L102',lambda:other.activate(self.code))
            self.authority.revoke(self.identifier)
            self.assertDenied('STC-L103',client.check)
            for route in ('/admin','/v1/issue','/v1/transfer'):
                with self.assertRaises(error.HTTPError) as caught:
                    request.urlopen(request.Request(url+route,data=b'{}',headers={'Content-Type':'application/json'}))
                self.assertEqual(caught.exception.code,404)
                caught.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)

    def test_provisioning_copies_only_public_material(self):
        package=self.root/'client/stc_statistics'
        package.mkdir(parents=True)
        (package/'app.py').write_text('')
        provision(self.authority,self.root/'client','https://license.example.test')
        self.assertEqual(set(p.name for p in package.iterdir()),{'app.py','license_config.json','license_trust.py'})
        self.assertNotIn('PRIVATE',(package/'license_trust.py').read_text())
        self.assertEqual(json.loads((package/'license_config.json').read_text())['server_url'],'https://license.example.test')
        provision_public({'server_url':'https://other.example.test','public_key':self.authority.public_key()},self.root/'client')
        self.assertEqual(json.loads((package/'license_config.json').read_text())['server_url'],'https://other.example.test')

    def test_unconfigured_release_blocked_before_package_creation(self):
        from make_patch import build_patch
        package=self.root/'client/stc_statistics'
        package.mkdir(parents=True)
        (package/'activation.py').write_text('')
        (package/'license_trust.py').write_text('PUBLIC_KEY = None')
        (package/'license_config.json').write_text('{"server_url":""}')
        with self.assertRaisesRegex(ValueError,'Release blocked'):
            build_patch(self.root/'client',self.root/'release','99.0.0',['0.5.5'])
        self.assertFalse((self.root/'release').exists())
        (package/'app.py').write_text('')
        provision(self.authority,self.root/'client','https://license.example.test')
        require_configured_release(self.root/'client')


class ActivationUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        settings=QSettings(str(Path(self.temp.name)/'settings.ini'),QSettings.Format.IniFormat)
        self.settings_patch=patch('stc_statistics.activation.QSettings',return_value=settings)
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)

    def pump(self,dialog):
        deadline=time.monotonic()+5
        while dialog.worker is not None and time.monotonic()<deadline:
            self.app.processEvents()
            time.sleep(.01)
        self.assertIsNone(dialog.worker)

    def test_dialog_cannot_accept_without_verification_and_is_bilingual(self):
        dialog=ActivationDialog(auto_check=False)
        dialog.accept()
        self.assertNotEqual(dialog.result(),QDialog.DialogCode.Accepted)
        self.assertIn('STC UNIC CODE',dialog.title.text())
        dialog.languages.setCurrentIndex(1)
        self.assertIn('Saisissez',dialog.title.text())
        dialog.code.setText('wrong')
        dialog.activate()
        self.assertFalse(dialog.verified)
        self.assertEqual(dialog.error_code,'invalid')
        dialog.close()

    def test_failed_check_has_safe_error_and_never_opens_workbench(self):
        def unavailable():
            raise RuntimeError('secret.example/private-token')
        dialog=ActivationDialog(client_factory=unavailable,auto_check=False)
        dialog.start_check()
        self.pump(dialog)
        self.assertFalse(dialog.verified)
        self.assertIn('STC-L104',dialog.status.text())
        self.assertNotIn('private-token',dialog.status.text())
        self.assertNotEqual(dialog.result(),QDialog.DialogCode.Accepted)
        dialog.close()

    def test_verified_check_unlocks_and_clears_code(self):
        class Verified:
            def check(self):
                return {'active':True}
        dialog=ActivationDialog(client_factory=Verified,auto_check=False)
        dialog.code.setText('private-code')
        dialog.start_check()
        self.pump(dialog)
        self.assertTrue(dialog.verified)
        self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.code.text(),'')

    def test_main_does_not_construct_workspace_on_rejected_activation(self):
        from stc_statistics import app as desktop
        with patch.object(desktop,'QApplication',return_value=self.app), \
             patch('stc_statistics.activation.ActivationDialog') as gate, \
             patch.object(desktop,'MainWindow') as window,patch.object(desktop.sys,'argv',['main.py']):
            gate.return_value.exec.return_value=QDialog.DialogCode.Rejected
            with self.assertRaises(SystemExit):
                desktop.main()
            window.assert_not_called()
