import asyncio
import base64
import unittest
from backend.native_transport import NativeTransport
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

    async def test_capture_kind_metadata_and_legacy_fallback(self):
        model=model_bytes(count=2)
        for reported, expected in [('mixed','mixed'),('curve','curve'),(None,'unknown')]:
            pending=asyncio.create_task(self.transport.request(self.target,'capture',with_metadata=True))
            await asyncio.sleep(0)
            job=self.transport.worker(self.target,self.token)
            value={'model':base64.b64encode(model).decode()}
            if reported: value['kind']=reported
            self.transport.worker(self.target,self.token,{'id':job['id'],'value':value})
            self.assertEqual(await pending,{'model':model,'kind':expected})

    async def test_encoding_probe_requires_capability_and_validates_receipt(self):
        from test_native_layout import report
        with self.assertRaisesRegex(ValueError,'更新内嵌插件'):
            await self.transport.request(self.target,'inspect-encoding')
        caps=['encoding-probe-v1']
        self.transport.worker(self.target,self.token,capabilities=caps)
        pending=asyncio.create_task(self.transport.request(self.target,'inspect-encoding'))
        await asyncio.sleep(0)
        job=self.transport.worker(self.target,self.token,capabilities=caps)
        self.transport.worker(self.target,self.token,{'id':job['id'],'value':report()},capabilities=caps)
        self.assertEqual(await pending,report())

    async def test_sample_collection_requires_new_capability_and_accepts_unknown_format(self):
        from test_model_samples import sample_report
        self.transport.worker(self.target,self.token,capabilities=['encoding-probe-v1'])
        with self.assertRaisesRegex(ValueError,'收集测试样本'):
            await self.transport.request(self.target,'inspect-encoding',include_models=True)
        self.assertFalse(self.transport.jobs)
        caps=['encoding-probe-v1','encoding-samples-v1']
        self.transport.worker(self.target,self.token,capabilities=caps)
        pending=asyncio.create_task(self.transport.request(self.target,'inspect-encoding',include_models=True))
        await asyncio.sleep(0)
        job=self.transport.worker(self.target,self.token,capabilities=caps)
        self.assertTrue(job['include_models'])
        value=sample_report(True)
        self.transport.worker(self.target,self.token,{'id':job['id'],'value':value},capabilities=caps)
        self.assertEqual(await pending,value)

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

    async def test_capture_format_diagnostic_reaches_caller_without_model_contents(self):
        model = model_bytes('PRIVATE_MODEL_NAME', source='PRIVATE_DOCUMENT_NAME')
        cases = [(model.replace(b'[]', b'xx', 1), '选择信息'),
                 (model.replace(b'PS\0\0\0', b'XX\0\0\0', 1), '几何数据'),
                 (model + b'PRIVATE_TRAILING_DATA', '尾部数据')]
        for data, stage in cases:
            pending = asyncio.create_task(self.transport.request(self.target, 'capture'))
            await asyncio.sleep(0)
            job = self.transport.worker(self.target, self.token)
            self.transport.worker(self.target, self.token, {
                'id': job['id'], 'value': {'model': base64.b64encode(data).decode()}})
            with self.assertRaises(ValueError) as caught:
                await pending
            message = str(caught.exception)
            self.assertIn(stage, message)
            self.assertIn('偏移', message)
            self.assertIn(f'共 {len(data)} 字节', message)
            self.assertNotIn('PRIVATE', message)
            self.assertNotIn(base64.b64encode(data).decode(), message)

    async def test_capture_encoding_error_is_distinct_from_model_format(self):
        pending = asyncio.create_task(self.transport.request(self.target, 'capture'))
        await asyncio.sleep(0)
        job = self.transport.worker(self.target, self.token)
        self.transport.worker(self.target, self.token, {'id': job['id'], 'value': {'model': '!invalid'}})
        with self.assertRaisesRegex(ValueError, '传输编码错误'):
            await pending

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

    async def test_long_poll_wakes_only_the_requested_window_and_sends_once(self):
        other='hwnd:43';other_token='b'*36
        self.transport.worker(other,other_token)
        first=asyncio.create_task(self.transport.poll(self.target,self.token,wait_ms=2000))
        second=asyncio.create_task(self.transport.poll(other,other_token,wait_ms=2000))
        await asyncio.sleep(.01)
        request=asyncio.create_task(self.transport.request(self.target,'insert',model_bytes()))
        job=await asyncio.wait_for(first,.2)
        self.assertEqual(job['action'],'insert')
        self.assertFalse(second.done())
        self.assertIsNone(self.transport.worker(self.target,self.token))
        self.transport.worker(self.target,self.token,{'id':job['id'],'value':{'started':True}})
        self.assertEqual(await request,{'started':True})
        second.cancel()
        await asyncio.gather(second,return_exceptions=True)

    async def test_long_poll_timeout_legacy_poll_and_validation(self):
        self.assertIsNone(await self.transport.poll(self.target,self.token,wait_ms=10))
        self.assertIsNone(await self.transport.poll(self.target,self.token))
        for wait in [-1,2001,'2000',True]:
            with self.assertRaises(ValueError):
                await self.transport.poll(self.target,self.token,wait_ms=wait)

    async def test_unsent_job_never_moves_to_replacement_session(self):
        pending=asyncio.create_task(self.transport.request(self.target,'insert',model_bytes()))
        await asyncio.sleep(0)
        self.transport.workers[self.target]['seen']-=6
        self.assertIsNone(self.transport.worker(self.target,'b'*36))
        with self.assertRaisesRegex(ValueError,'连接已更换'): await pending
        self.assertFalse(self.transport.jobs)

    async def test_sent_job_is_not_replayed_to_replacement_session(self):
        pending=asyncio.create_task(self.transport.request(self.target,'insert',model_bytes()))
        await asyncio.sleep(0)
        job=self.transport.worker(self.target,self.token)
        self.transport.workers[self.target]['seen']-=6
        self.assertIsNone(self.transport.worker(self.target,'b'*36))
        with self.assertRaisesRegex(ValueError,'连接已更换'): await pending
        with self.assertRaisesRegex(ValueError,'已有模型连接'):
            self.transport.worker(self.target,self.token,{'id':job['id'],'value':{'started':True}})

    async def test_expired_old_poll_cannot_reclaim_replaced_session(self):
        old=asyncio.create_task(self.transport.poll(self.target,self.token,wait_ms=30))
        await asyncio.sleep(0)
        self.transport.workers[self.target]['seen']-=6
        self.transport.worker(self.target,'b'*36)
        self.assertIsNone(await old)
        self.assertEqual(self.transport.workers[self.target]['token'],'b'*36)

    async def test_sent_timeout_blocks_only_that_window_until_matching_receipt(self):
        self.transport.request_timeout=.02
        pending=asyncio.create_task(self.transport.request(self.target,'insert',model_bytes()))
        await asyncio.sleep(0)
        job=self.transport.worker(self.target,self.token)
        with self.assertRaisesRegex(ValueError,'超时'): await pending
        with self.assertRaisesRegex(ValueError,'尚未确认'):
            await self.transport.request(self.target,'insert',model_bytes())
        self.transport.worker('hwnd:43','b'*36,{'id':job['id'],'value':{'started':True}})
        self.assertIn(job['id'],self.transport.jobs)
        # Only the first request exercises timeout; allow scheduler jitter for the healthy window.
        self.transport.request_timeout=1
        other=asyncio.create_task(self.transport.request('hwnd:43','insert',model_bytes()))
        await asyncio.sleep(0)
        other_job=self.transport.worker('hwnd:43','b'*36)
        self.transport.worker('hwnd:43','b'*36,{'id':other_job['id'],'value':{'started':True}})
        self.assertEqual(await other,{'started':True})
        self.assertIsNone(self.transport.worker(self.target,self.token))
        self.transport.worker(self.target,self.token,{'id':job['id'],'error':'late failure'})
        self.assertFalse(self.transport.jobs)

    async def test_unsent_timeout_can_be_retried_without_delayed_delivery(self):
        self.transport.request_timeout=.01
        with self.assertRaisesRegex(ValueError,'超时'):
            await self.transport.request(self.target,'insert',model_bytes())
        self.assertFalse(self.transport.jobs)
        self.assertIsNone(self.transport.worker(self.target,self.token))

    async def test_caller_cancel_keeps_sent_job_until_receipt(self):
        pending=asyncio.create_task(self.transport.request(self.target,'insert',model_bytes()))
        await asyncio.sleep(0)
        job=self.transport.worker(self.target,self.token)
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError): await pending
        self.assertIn(job['id'],self.transport.jobs)
        with self.assertRaisesRegex(ValueError,'尚未确认'):
            await self.transport.request(self.target,'capture')
        self.transport.worker(self.target,self.token,{'id':job['id'],'value':{'started':True}})
        self.assertFalse(self.transport.jobs)

    async def test_unmatched_or_unsent_receipt_cannot_complete_a_job(self):
        pending=asyncio.create_task(self.transport.request(self.target,'insert',model_bytes()))
        await asyncio.sleep(0)
        job_id=next(iter(self.transport.jobs))
        job=self.transport.worker(self.target,self.token,{'id':job_id,'value':{'started':True}})
        self.assertFalse(pending.done())
        self.assertEqual(job['id'],job_id)
        self.transport.worker(self.target,self.token,{'id':job_id,'value':{'started':True}})
        await pending
