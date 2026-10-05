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
    async def test_asset_rebase_requires_new_plugin_and_transfers_saved_model(self):
        from model_fixture import model_bytes
        model=model_bytes()
        self.transport.worker(self.target,self.token,capabilities=['base-point-v1'])
        with self.assertRaisesRegex(ValueError,'自动基点插件'):
            await self.transport.request(self.target,'rebase',model,base_mode='pick')
        caps=['base-point-v1','asset-base-point-v1']
        self.transport.worker(self.target,self.token,capabilities=caps)
        pending=asyncio.create_task(self.transport.request(self.target,'rebase',model,base_mode='pick'))
        await asyncio.sleep(0)
        job=self.transport.worker(self.target,self.token,capabilities=caps)
        self.assertEqual(base64.b64decode(job['model']),model)
        self.assertEqual(job['action'],'rebase')
        self.transport.worker(self.target,self.token,{'id':job['id'],'value':{'model':job['model']}},capabilities=caps)
        self.assertEqual(await pending,model)
        self.assertFalse(self.transport.jobs)

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
    async def test_offline_point_is_atomic_and_preserves_orientation_geometry_and_package(self):
        from model_fixture import model_bytes
        from unittest.mock import AsyncMock
        from backend.model_clipboard import model_base_point
        original=struct.pack('<7d',1,2,3,0.1,0.2,0.3,0.9)+model_bytes('offline')[56:]
        asset=self.service.library.add(original,{'name':'offline','kind':'curve'})
        self.service.model_enabled=False
        self.service.native.request=AsyncMock(side_effect=AssertionError('Native app is not required'))
        point=await self.call('library.base_point',{'id':asset['id']})
        self.assertEqual(point['base_point'],[1,2,3])
        updated=await self.call('library.update',{'id':asset['id'],'name':'edited','base_point':[-12.5,4,9],'model_digest':point['digest']})
        actual=bytes(self.service.library.get(asset['id'])['model'])
        self.assertEqual(model_base_point(actual),[-12.5,4,9])
        self.assertEqual(actual[24:],original[24:])
        self.assertEqual(updated['base_point'],[-12.5,4,9])
        imported=self.service.library.import_package(self.service.library.export(asset['id']))
        self.assertEqual(bytes(self.service.library.get(imported['id'])['model']),actual)
        self.service.native.request.assert_not_called()
        self.assertEqual(self.desktop.calls,[])

    async def test_offline_invalid_or_stale_point_does_not_change_model_or_metadata(self):
        from model_fixture import model_bytes
        asset=self.service.library.add(model_bytes(),{'name':'original'})
        before=bytes(self.service.library.get(asset['id'])['model'])
        for point in [[float('nan'),0,0],[True,0,0],[1,2],[1e13,0,0],['1',0,0]]:
            with self.assertRaisesRegex(ValueError,'有限坐标'):
                await self.call('library.update',{'id':asset['id'],'name':'wrong','base_point':point,'model_digest':asset['digest']})
        with self.assertRaisesRegex(ValueError,'组件已变化'):
            await self.call('library.update',{'id':asset['id'],'name':'wrong','base_point':[1,2,3],'model_digest':'stale'})
        self.assertEqual(self.service.library.details(asset['id'])['name'],'original')
        self.assertEqual(bytes(self.service.library.get(asset['id'])['model']),before)
    async def test_native_capture_and_rebase_preserve_bodies_and_package(self):
        from unittest.mock import AsyncMock
        from model_fixture import model_bytes
        original=model_bytes('original',count=2)
        asset=self.service.library.add(original,{'name':'original'})
        reference=struct.pack('<7d',12,24,36,0,0,0,1)+model_bytes('reference')[56:]
        self.service.native.request=AsyncMock(return_value=reference)
        updated=await self.call('library.rebase',{'id':asset['id'],'target_id':'hwnd:42','base_mode':'pick'})
        self.service.native.request.assert_awaited_once_with('hwnd:42','rebase',original,base_mode='pick')
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
    def test_preview_coordinates_and_ray_cast(self):
        subprocess.run(['node','tests/test_preview_base_point.mjs'],cwd=Path(__file__).resolve().parents[1],capture_output=True,check=True,timeout=10)
    def test_automatic_reference(self):
        subprocess.run(['node','tests/test_auto_base_point.js'],cwd=Path(__file__).resolve().parents[1],capture_output=True,check=True,timeout=10)

    def test_native_point_command(self):
        subprocess.run(['node','tests/test_base_point.js'],cwd=Path(__file__).resolve().parents[1],capture_output=True,check=True,timeout=10)
