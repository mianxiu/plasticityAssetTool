import asyncio
import json
from unittest.mock import patch
from tornado.testing import gen_test, AsyncHTTPTestCase
from tornado.websocket import websocket_connect
import test_http_api as http_tests


class LibraryChangesTests(AsyncHTTPTestCase):
    get_app = http_tests.HttpTests.get_app
    def tearDown(self):
        super().tearDown()
        self.directory.cleanup()
    @gen_test
    async def test_delta_update_move_archive_and_restart_cursor(self):
        app = self._app
        first = await app.dispatch('library.changes', {})
        self.assertTrue(first['full'])
        asset = self.service.library.add(b'test-only', {'name':'one'})
        app.record_library_change(asset['id'])
        delta = await app.dispatch('library.changes', {'since':first['revision']})
        self.assertFalse(delta['full'])
        self.assertEqual([row['id'] for row in delta['changed']], [asset['id']])
        await app.dispatch('library.update', {'id':asset['id'],'name':'updated'})
        changed = await app.dispatch('library.changes', {'since':delta['revision']})
        self.assertEqual(changed['changed'][0]['name'], 'updated')
        await app.dispatch('library.archive', {'id':asset['id']})
        archived = await app.dispatch('library.changes', {'since':changed['revision']})
        self.assertEqual(archived['removed'], [asset['id']])
        full_archive = await app.dispatch('library.changes', {'archived':True})
        self.assertEqual(len(full_archive['assets']),1)
        self.assertTrue((await app.dispatch('library.changes', {'since':'other-process:0'}))['full'])
        self.assertTrue((await app.dispatch('library.changes', {'since':app.library_generation+':9999'}))['full'])

    @gen_test
    async def test_unchanged_cursor_avoids_full_asset_scan_and_expired_cursor_recovers(self):
        app = self._app
        first = await app.dispatch('library.changes', {})
        with patch.object(self.service.library, 'list', side_effect=AssertionError('full scan')):
            same = await app.dispatch('library.changes', {'since':first['revision']})
        self.assertFalse(same['full']); self.assertEqual(same['changed'],[])
        asset = self.service.library.add(b'test-only', {'name':'one'})
        for _ in range(513): app.record_library_change(asset['id'])
        self.assertTrue((await app.dispatch('library.changes', {'since':first['revision']}))['full'])

    @gen_test
    async def test_reads_do_not_broadcast_change_and_mutation_does(self):
        socket = await websocket_connect(self.get_url('/websocket').replace('http','ws',1))
        await socket.read_message()
        try:
            for action in ('library.state','library.changes','library.list','folder.list'):
                await socket.write_message(json.dumps({'id':action,'action':action,'args':{}}))
                self.assertEqual(json.loads(await socket.read_message())['type'],'response')
            # The next response must not be preceded by a read-triggered event.
            await socket.write_message(json.dumps({'id':'create','action':'collection.create','args':{'name':'Test'}}))
            self.assertEqual(json.loads(await socket.read_message())['id'],'create')
            self.assertEqual(json.loads(await socket.read_message())['type'],'library_changed')
        finally:
            socket.close()
