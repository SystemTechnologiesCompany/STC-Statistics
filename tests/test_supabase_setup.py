import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from stc_statistics.licensing import LicenseClient,CredentialStore,LicenseError,require_configured_release
import supabase_setup as setup


class SupabaseSetupTests(unittest.TestCase):
    def test_dashboard_bundle_matches_sources_and_has_no_external_import(self):
        source=setup.dashboard_source()
        self.assertNotIn('import ',source)
        self.assertIn('Deno.serve(createHandler',source)
        checked_in=(setup.ROOT/'supabase/dashboard/stc-license.ts').read_text(encoding='utf-8')
        self.assertEqual(source,checked_in)

    def test_node_signed_response_verifies_with_real_windows_client(self):
        node=shutil.which('node')
        if not node:
            self.skipTest('Node is needed for cross-runtime signing')
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
            private=folder/'key.pem'
            private.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
            import hashlib
            numbers=key.public_key().public_numbers()
            public={'n':format(numbers.n,'x'),'e':numbers.e,'key_id':hashlib.sha256(key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)).hexdigest()[:24]}
            client=LicenseClient(setup.URL,public,CredentialStore(folder/'activation.bin'),identity='a'*64)
            protocol=(setup.ROOT/'supabase/functions/stc-license/protocol.ts').as_uri()
            # Secret material is read from the temporary file, never command arguments/stdout.
            script="import {readFileSync} from 'node:fs'; import {loadSigner} from "+json.dumps(protocol)+"; const sign=await loadSigner(readFileSync(process.argv[1],'utf8')); const now=Math.floor(Date.now()/1000); console.log(JSON.stringify(await sign({type:'stc-license-access-v1',active:true,device_id:'a'.repeat(64),nonce:'b'.repeat(48),license_id:'12345678-1234-1234-1234-123456789abc',issued_at:now,expires_at:now+300})));"
            result=subprocess.run([node,'--input-type=module','-e',script,str(private)],capture_output=True,text=True,timeout=20,check=True)
            envelope=json.loads(result.stdout)
            self.assertTrue(client.verify(envelope,'b'*48)['active'])
            envelope['payload']['device_id']='c'*64
            with self.assertRaises(LicenseError):
                client.verify(envelope,'b'*48)

    def test_live_verify_never_configures_client_on_failed_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            (folder/'license-public.json').write_text(json.dumps({'server_url':setup.URL,'public_key':{}}))
            with patch.object(setup,'PRIVATE',folder),patch.object(setup.getpass,'getpass',return_value='private-test-code'), \
                 patch.object(setup,'LicenseClient') as client,patch.object(setup,'provision_public') as provision:
                client.return_value.activate.side_effect=LicenseError('STC-L104')
                with self.assertRaises(LicenseError):
                    setup.verify()
                provision.assert_not_called()

    def test_unverified_supabase_project_still_cannot_be_released(self):
        # Project URL alone is not sufficient: the trusted public key is absent.
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            package=root/'stc_statistics'
            package.mkdir()
            (package/'activation.py').write_text('')
            (package/'license_config.json').write_text(json.dumps({'server_url':setup.URL}))
            (package/'license_trust.py').write_text('PUBLIC_KEY = None')
            with self.assertRaisesRegex(ValueError,'Release blocked'):
                require_configured_release(root)
