import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('stc_build_installer',ROOT/'packaging/build_installer.py')
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        app=self.root/'stc_statistics'
        app.mkdir()
        key={'n':format((1<<3071)+1,'x'),'e':65537,'key_id':'a'*24}
        (app/'activation.py').write_text('# activation')
        (app/'app.py').write_text('# current licensed application')
        (app/'version.py').write_text('APP_VERSION = '+repr(builder.APP_VERSION))
        (app/'license_config.json').write_text(json.dumps({'server_url':'https://license.example.test'}))
        (app/'license_trust.py').write_text('PUBLIC_KEY = '+repr(key))
        (self.root/'main.py').write_text('# licensed entry point')
        (self.root/'packaging').mkdir()
        (self.root/'packaging/stc-statistics-desktop.ico').write_bytes(b'fixture icon')
        (self.root/'dist').mkdir()
        (self.root/'licensing_server').mkdir()
        (self.root/'licensing_server/private-secret.env').write_text('never ship')
        (self.root/'.licensing_private').mkdir()
        (self.root/'.licensing_private/signing-key.pem').write_text('never ship')
        self.payload=self.root/'runtime.zip'
        with zipfile.ZipFile(self.payload,'w') as z:
            z.writestr('python.exe',b'private Python fixture')
            z.writestr('pythonw.exe',b'private Python GUI fixture')
            z.writestr('python314._pth','app\nimport site\n')
            z.writestr('app/main.py','# OLD UNLICENSED ENTRY')
            z.writestr('app/old-only.py','# old code')
            z.writestr('Lib/site-packages/certifi/cacert.pem','PUBLIC CERTIFICATE')
            z.writestr('Lib/site-packages/example.dist-info/LICENSE','retained vendor terms')
        self.metadata={'payload_sha256':builder.digest(self.payload)}
        (self.root/'dist/STC_Statistics_build.json').write_text(json.dumps(self.metadata))

    def stage(self):
        target=self.root/'stage'
        builder.stage_payload(self.root,target,self.payload)
        return target

    def test_installer_uses_current_licensed_app_and_only_the_existing_runtime(self):
        stage=self.stage()
        self.assertEqual((stage/'runtime/app/main.py').read_text(),'# licensed entry point')
        self.assertFalse((stage/'runtime/app/old-only.py').exists())
        self.assertFalse((stage/'runtime/app/licensing_server').exists())
        self.assertFalse((stage/'runtime/app/.licensing_private').exists())
        self.assertTrue((stage/'runtime/Lib/site-packages/example.dist-info/LICENSE').is_file())
        self.assertTrue((stage/'runtime/Lib/site-packages/certifi/cacert.pem').is_file())
        self.assertEqual((stage/'runtime/.complete').read_text(),self.metadata['payload_sha256'])
        self.assertEqual(builder.validate_stage(stage),builder.APP_VERSION)

    def test_runtime_checksum_failure_does_not_stage_anything(self):
        self.payload.write_bytes(self.payload.read_bytes()+b'corrupt')
        with self.assertRaisesRegex(ValueError,'verified build metadata'):
            self.stage()
        self.assertFalse((self.root/'stage').exists())

    def test_path_traversal_is_rejected(self):
        for name in ('../secret','/absolute','C:/absolute','Lib/../../secret','Lib\\bad'):
            with self.assertRaises(ValueError):
                builder.runtime_entry(name)
        self.assertFalse(builder.runtime_entry('app/main.py'))
        self.assertTrue(builder.runtime_entry('Lib/site-packages/pandas/__init__.py'))

    def test_credentials_and_signing_keys_cannot_be_packaged(self):
        stage=self.stage()
        for name in ('signing-key.pem','activation.bin','.env','test.stcp'):
            private=stage/'runtime/app/stc_statistics'/name
            private.write_text('private fixture')
            with self.assertRaisesRegex(ValueError,'Private material'):
                builder.validate_stage(stage)
            private.unlink()

    def test_installer_preserves_user_data_and_blocks_downgrades(self):
        script=(ROOT/'packaging/installer.iss').read_text(encoding='utf-8')
        self.assertIn('PrivilegesRequired=lowest',script)
        self.assertIn('ArchitecturesAllowed=x64compatible',script)
        self.assertIn('MinVersion=10.0.17763',script)
        self.assertIn('EncodeVer(7, 0, 0)',script)
        self.assertIn('ComparePackedVersion(Existing, Candidate) > 0',script)
        cleanup=script.split('[UninstallDelete]',1)[1].split('[Code]',1)[0]
        self.assertIn('Name: "{app}\\runtime"',cleanup)
        self.assertNotIn('Name: "{app}"',cleanup)
        self.assertNotIn('Name: "{app}\\licensing"',cleanup)
        self.assertNotIn('Name: "{app}\\updates"',cleanup)
