import json
import tempfile
from tornado.testing import AsyncHTTPTestCase, gen_test
from test_service_control import make_application


class DataTransferHttpTests(AsyncHTTPTestCase):
    def get_app(self):
        self.temp=tempfile.TemporaryDirectory()
        return make_application(self.temp.name)

    def tearDown(self):
        for token in list(self._app.transfers.plans):
            self._app.transfers.discard(token)
        super().tearDown()
        self.temp.cleanup()

    def upload(self,payload,kind='import'):
        boundary='transfer-boundary'
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="kind"\r\n\r\n{kind}\r\n'
              f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="input.zip"\r\nContent-Type: application/zip\r\n\r\n').encode()+payload+f'\r\n--{boundary}--\r\n'.encode()
        return self.fetch('/api/data/preview',method='POST',body=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary})

    def commit(self,request):
        return self.fetch('/api/data/commit',method='POST',body=json.dumps(request),headers={'Content-Type':'application/json'})

    def test_restore_confirmation_and_cursor_reset(self):
        library=self._app.service.library
        original=library.add(b'native bytes',{'name':'A'})
        before=self._app.library_generation
        backup=self.fetch('/api/data/backup')
        self.assertEqual(backup.code,200)
        self.assertIn('attachment',backup.headers['Content-Disposition'])
        library.add(b'extra',{'name':'B'})
        preview=self.upload(backup.body,'restore')
        self.assertEqual(preview.code,200)
        plan=json.loads(preview.body)['data']
        self.assertEqual(self.commit({'token':plan['token']}).code,400)
        self.assertEqual(len(library.list()),2)
        self.assertEqual(self.commit({'token':plan['token'],'confirm_restore':True}).code,200)
        self.assertEqual(len(library.list()),1)
        self.assertEqual(library.get(original['id'])['model'],b'native bytes')
        self.assertNotEqual(before,self._app.library_generation)

    def test_batch_commit_cancel_and_origin_restrictions(self):
        library=self._app.service.library
        asset=library.add(b'native',{'name':'A'})
        with library.export_batch([asset['id']])[0] as output:
            payload=output.read()
        plan=json.loads(self.upload(payload).body)['data']
        self.assertEqual(len(library.list()),1)
        self.assertEqual(self.commit({'token':plan['token'],'choices':[{'mode':'copy'}]}).code,200)
        self.assertEqual(len(library.list()),2)
        plan=json.loads(self.upload(payload).body)['data']
        cancel=self.fetch('/api/data/cancel',method='POST',body=json.dumps({'token':plan['token']}))
        self.assertEqual(cancel.code,200)
        self.assertEqual(self.commit({'token':plan['token'],'choices':[{'mode':'copy'}]}).code,400)
        for operation in ('preview','commit','cancel'):
            self.assertEqual(self.fetch('/api/data/'+operation,method='POST',body='{}',headers={'Origin':'https://example.com'}).code,403)
        self.assertEqual(self.fetch('/api/data/backup',headers={'Origin':'https://example.com'}).code,403)

    def test_commit_blocked_during_model_job(self):
        library=self._app.service.library
        asset=library.add(b'native',{'name':'A'})
        with library.export_batch([asset['id']])[0] as output:
            payload=output.read()
        plan=json.loads(self.upload(payload).body)['data']
        self._app.service.geometry.jobs['running']={}
        try:
            self.assertEqual(self.commit({'token':plan['token'],'choices':[{'mode':'copy'}]}).code,400)
        finally:
            self._app.service.geometry.jobs.clear()
        self.assertEqual(len(library.list()),1)

    @gen_test
    async def test_removed_library_falls_back_after_restore(self):
        state=await self._app.dispatch('library.changes',{'library_id':'missing'})
        self.assertEqual(state['library_id'],'default')
        self.assertTrue(state['full'])
