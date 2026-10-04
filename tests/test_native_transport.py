import asyncio
import base64
import unittest
from native_transport import NativeTransport
from model_fixture import model_bytes
from test_group_recipe import recipe


class NativeTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.transport=NativeTransport()
        self.target='hwnd:42'
        self.token='a'*36
        self.transport.worker(self.target,self.token)

    async def test_capture_validates_model_and_ignores_other_windows(self):
        pending=asyncio.create_task(self.transport.request(self.target,'capture'))
        await asyncio.sleep(0)
        job=self.transport.worker(self.target,self.token)
        model=model_bytes('native')
        result={'id':job['id'],'value':{'model':base64.b64encode(model).decode()}}
        self.transport.worker('hwnd:43',self.token,result)
        self.assertFalse(pending.done())
        self.transport.worker(self.target,self.token,result)
        self.assertEqual(await pending,model)

    async def test_group_capture_and_inspection_keep_metadata_window_bound(self):
        self.transport.worker(self.target,self.token,capabilities=['group-recipe-v1'])
        for action,payload,expected in [
            ('inspect-group',{'recipe':recipe(),'signature':'selection'}, {'recipe':recipe(),'signature':'selection'}),
            ('capture-group',{'model':base64.b64encode(model_bytes(count=2)).decode(),'recipe':recipe()}, {'model':model_bytes(count=2),'recipe':recipe()}),
        ]:
            pending=asyncio.create_task(self.transport.request(self.target,action,signature='selection'))
            await asyncio.sleep(0)
            job=self.transport.worker(self.target,self.token,capabilities=['group-recipe-v1'])
            self.transport.worker(self.target,self.token,{'id':job['id'],'value':payload},capabilities=['group-recipe-v1'])
            self.assertEqual(await pending,expected)

    async def test_recipe_requires_capability_before_queueing(self):
        with self.assertRaisesRegex(ValueError,'组运算插件'):
            await self.transport.request(self.target,'insert',model_bytes(count=2),recipe=recipe())
        self.assertFalse(self.transport.jobs)
        self.transport.worker(self.target,self.token,capabilities=['group-recipe-v1'])
        with self.assertRaisesRegex(ValueError,'定位置入'):
            await self.transport.request(self.target,'insert',model_bytes(count=2),False,recipe=recipe())
        self.assertFalse(self.transport.jobs)

    async def test_insert_delivered_once_and_rejects_concurrent_command(self):
        model=model_bytes('saved')
        pending=asyncio.create_task(self.transport.request(self.target,'insert',model))
        await asyncio.sleep(0)
        with self.assertRaisesRegex(ValueError,'正在处理'):
            await self.transport.request(self.target,'insert',model)
        job=self.transport.worker(self.target,self.token)
        self.assertEqual(base64.b64decode(job['model']),model)
        self.assertIsNone(self.transport.worker(self.target,self.token))
        self.transport.worker(self.target,self.token,{'id':job['id'],'value':{'started':True}})
        self.assertEqual(await pending,{'started':True})

    async def test_invalid_capture_and_disconnected_target(self):
        pending=asyncio.create_task(self.transport.request(self.target,'capture'))
        await asyncio.sleep(0)
        job=self.transport.worker(self.target,self.token)
        self.transport.worker(self.target,self.token,{'id':job['id'],'value':{'model':'bm90IGEgbW9kZWw='}})
        with self.assertRaisesRegex(ValueError,'数据无效'): await pending
        with self.assertRaisesRegex(ValueError,'未连接'):
            await self.transport.request('hwnd:999','capture')

    async def test_bad_model_never_queued_and_wrong_token_rejected(self):
        with self.assertRaises(ValueError):await self.transport.request(self.target,'insert',b'bad')
        self.assertFalse(self.transport.jobs)
        with self.assertRaises(ValueError):self.transport.worker(self.target,'b'*36)

    async def test_boolean_mode_requires_updated_worker_and_passes_preset(self):
        model=model_bytes('cutter')
        with self.assertRaisesRegex(ValueError,'布尔置入插件'):
            await self.transport.request(self.target,'insert',model,True,'difference')
        self.assertFalse(self.transport.jobs)
        self.transport.worker(self.target,self.token,capabilities=['boolean-placement-v1'])
        task=asyncio.create_task(self.transport.request(self.target,'insert',model,True,'difference'))
        await asyncio.sleep(0)
        job=self.transport.worker(self.target,self.token,capabilities=['boolean-placement-v1'])
        self.assertEqual(job['insert_mode'],'difference')
        self.transport.worker(self.target,self.token,{'id':job['id'],'value':{'started':True}})
        await task
        with self.assertRaisesRegex(ValueError,'定位置入'):
            await self.transport.request(self.target,'insert',model,False,'union')
        with self.assertRaisesRegex(ValueError,'默认置入模式'):
            await self.transport.request(self.target,'insert',model,True,'invalid')

    async def test_error_stack_is_not_shown_to_user(self):
        pending=asyncio.create_task(self.transport.request(self.target,'capture'))
        await asyncio.sleep(0)
        job=self.transport.worker(self.target,self.token)
        self.transport.worker(self.target,self.token,{'id':job['id'],'error':'Error: 当前偏移操作尚未结束\n    at insertModel (C:/Temp/internal.cjs:89:87)'})
        with self.assertRaises(ValueError) as caught: await pending
        self.assertEqual(str(caught.exception),'当前偏移操作尚未结束')

    async def test_two_windows_never_consume_each_others_insertions(self):
        other='hwnd:43';other_token='b'*36
        self.transport.worker(other,other_token)
        first=asyncio.create_task(self.transport.request(self.target,'insert',model_bytes('first')))
        second=asyncio.create_task(self.transport.request(other,'insert',model_bytes('second')))
        await asyncio.sleep(0)
        second_job=self.transport.worker(other,other_token)
        first_job=self.transport.worker(self.target,self.token)
        self.assertEqual(base64.b64decode(first_job['model']),model_bytes('first'))
        self.assertEqual(base64.b64decode(second_job['model']),model_bytes('second'))
        self.transport.worker(other,other_token,{'id':first_job['id'],'value':{'started':True}})
        self.assertFalse(first.done())
        self.transport.worker(self.target,self.token,{'id':first_job['id'],'value':{'started':True}})
        self.transport.worker(other,other_token,{'id':second_job['id'],'value':{'started':True}})
        await first;await second
