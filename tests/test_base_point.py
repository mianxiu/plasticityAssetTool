import base64
import asyncio
import struct
import subprocess
import unittest
from pathlib import Path
import test_asset_service as service_tests
import test_native_transport as transport_tests


class BasePointNativeTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = transport_tests.NativeTransportTests.asyncSetUp
    async def test_point_capture_requires_capability_and_passes_mode(self):
        with self.assertRaisesRegex(ValueError, '基点插件'):
            await self.transport.request(self.target, 'capture', base_mode='pick')
        self.transport.worker(self.target,self.token,capabilities=['base-point-v1'])
        pending=asyncio.create_task(self.transport.request(self.target,'capture',base_mode='pick'))
        await asyncio.sleep(0)
        job=self.transport.worker(self.target,self.token,capabilities=['base-point-v1'])
        self.assertEqual(job['base_mode'],'pick')
        self.transport.worker(self.target,self.token,{'id':job['id'],'error':'cancelled'},capabilities=['base-point-v1'])
        with self.assertRaisesRegex(ValueError,'cancelled'):
            await pending
        self.assertFalse(self.transport.jobs)


class BasePointServiceTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = service_tests.ServiceTests.asyncSetUp
    asyncTearDown = service_tests.ServiceTests.asyncTearDown
    call = service_tests.ServiceTests.call
    async def test_native_capture_and_rebase_preserve_bodies_and_package(self):
        from unittest.mock import AsyncMock
        from model_fixture import model_bytes
        original=model_bytes('original',count=2)
        asset=self.service.library.add(original,{'name':'original'})
        reference=struct.pack('<7d',12,24,36,0,0,0,1)+model_bytes('reference')[56:]
        self.service.native.request=AsyncMock(return_value=reference)
        updated=await self.call('library.rebase',{'id':asset['id'],'target_id':'hwnd:42','base_mode':'pick'})
        self.service.native.request.assert_awaited_once_with('hwnd:42','capture',base_mode='pick')
        actual=bytes(self.service.library.get(asset['id'])['model'])
        self.assertEqual(actual[:56],reference[:56])
        self.assertEqual(actual[56:],original[56:])
        self.assertNotEqual(updated['digest'],asset['digest'])
        imported=self.service.library.import_package(self.service.library.export(asset['id']))
        self.assertEqual(bytes(self.service.library.get(imported['id'])['model']),actual)
        self.assertEqual(self.desktop.calls,[])

    async def test_save_with_base_point_forwards_native_capture_mode(self):
        from unittest.mock import AsyncMock
        from model_fixture import model_bytes
        self.service.native.worker('hwnd:42','a'*36,capabilities=['selection-kind-v1','base-point-v1'])
        self.service.native.request=AsyncMock(return_value={'model':model_bytes(),'kind':'solid'})
        await self.call('library.capture',{'name':'picked','copy_selection':True,'transport':'native','target_id':'hwnd:42','preview_mode':'geometry','base_mode':'pick'})
        self.service.native.request.assert_awaited_once_with('hwnd:42','capture',with_metadata=True,base_mode='pick')

    async def test_concurrent_model_change_is_not_overwritten(self):
        from unittest.mock import AsyncMock
        from model_fixture import model_bytes
        import hashlib
        asset=self.service.library.add(model_bytes(),{'name':'original'})
        changed=model_bytes('changed')
        async def capture(*args,**kwargs):
            with self.service.library.connect() as db:
                db.execute('UPDATE assets SET model=?,digest=? WHERE id=?',(changed,hashlib.sha256(changed).hexdigest(),asset['id']))
            return model_bytes('reference')
        self.service.native.request=AsyncMock(side_effect=capture)
        with self.assertRaisesRegex(ValueError,'拾取期间已变化'):
            await self.call('library.rebase',{'id':asset['id'],'target_id':'hwnd:42','base_mode':'pick'})
        self.assertEqual(bytes(self.service.library.get(asset['id'])['model']),changed)

    async def test_cancel_or_pause_leaves_component_unchanged(self):
        from unittest.mock import AsyncMock
        from model_fixture import model_bytes
        asset=self.service.library.add(model_bytes(),{'name':'original'})
        before=bytes(self.service.library.get(asset['id'])['model'])
        self.service.native.request=AsyncMock(side_effect=ValueError('cancelled'))
        with self.assertRaisesRegex(ValueError,'cancelled'):
            await self.call('library.rebase',{'id':asset['id'],'target_id':'hwnd:42','base_mode':'pick'})
        self.assertEqual(bytes(self.service.library.get(asset['id'])['model']),before)
        self.service.model_enabled=False
        with self.assertRaisesRegex(ValueError,'暂停'):
            await self.call('library.rebase',{'id':asset['id'],'target_id':'hwnd:42','base_mode':'world'})


class BasePointJavascriptTests(unittest.TestCase):
    def test_native_point_command(self):
        subprocess.run(['node','tests/test_base_point.js'],cwd=Path(__file__).resolve().parents[1],capture_output=True,check=True,timeout=10)
