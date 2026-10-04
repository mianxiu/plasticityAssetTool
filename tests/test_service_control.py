import asyncio
import json
import struct
import tempfile
import unittest
from pathlib import Path
from asset_service import AssetService
from main import Application, DEFAULT_SHORTCUTS, StaticHandler
from tornado import web
from service_tray import icon_bitmap
from test_asset_service import FakeDesktop
from model_fixture import model_bytes
from tornado.testing import AsyncHTTPTestCase


def make_application(directory):
    config={"server":{"http_port":15150},"plasticity":{"cdp_endpoints":[]},"keymap":{"desktop_shortcuts":DEFAULT_SHORTCUTS}}
    desktop=FakeDesktop()
    return Application(config,AssetService(config,directory,desktop=desktop))


class ServiceControlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.app=make_application(self.directory.name)
        self.service=self.app.service
        self.asset=self.service.library.add(model_bytes(),{"name":"component"})

    async def asyncTearDown(self):
        self.directory.cleanup()

    async def test_pause_blocks_native_operations_but_preserves_browsing_and_resume(self):
        state=await self.app.dispatch('service.status',{})
        self.assertEqual(state['component_count'],1)
        self.assertEqual(len(state['targets']),1)
        await self.app.dispatch('service.connection',{'enabled':False})
        for action,args in [('asset.insert',{'id':self.asset['id'],'target_id':'hwnd:42'}),('target.command',{'action':'scale','target_id':'hwnd:42'}),('library.capture',{'copy_selection':True,'name':'test','target_id':'hwnd:42'})]:
            with self.assertRaisesRegex(ValueError,'暂停'):
                await self.app.dispatch(action,args)
        self.assertEqual(self.service.desktop.calls,[])
        self.assertEqual(len(await self.app.dispatch('library.list',{})),1)
        self.assertFalse((await self.app.dispatch('state',{}))['model_enabled'])
        await self.app.dispatch('service.connection',{'enabled':True})
        await self.app.dispatch('asset.insert',{'id':self.asset['id'],'target_id':'hwnd:42'})
        self.assertIn(('shortcut',42,'ctrl+shift+v'),self.service.desktop.calls)

    async def test_quit_waits_for_operation_and_disables_new_model_requests(self):
        await self.service.lock.acquire()
        pending=asyncio.create_task(self.app.dispatch('service.quit',{}))
        await asyncio.sleep(0)
        self.assertFalse(pending.done())
        self.assertFalse(self.app.stop_event.is_set())
        self.service.lock.release()
        await pending
        self.assertFalse(self.service.model_enabled)
        self.assertFalse(self.app.stop_event.is_set())
        await asyncio.wait_for(self.app.stop_event.wait(),1)
        self.assertEqual(self.service.library.get(self.asset['id'])['model'],model_bytes())

    async def test_focus_validates_current_window_without_sending_model_commands(self):
        await self.app.dispatch('service.focus',{'target_id':'hwnd:42'})
        self.assertEqual(self.service.desktop.calls,[('activate',42)])
        with self.assertRaises(ValueError):
            await self.app.dispatch('service.focus',{'target_id':'missing'})

    def test_tray_icons_have_correct_windows_bitmap_and_status_variants(self):
        active,paused=icon_bitmap(),icon_bitmap(True)
        self.assertEqual(struct.unpack_from('<IiiHH',active),(40,32,64,1,32))
        self.assertEqual(len(active),40+32*32*4+128)
        self.assertNotEqual(active,paused)


class ServiceHttpTests(AsyncHTTPTestCase):
    def get_app(self):
        self.directory=tempfile.TemporaryDirectory()
        return make_application(self.directory.name)

    def tearDown(self):
        super().tearDown()
        self.directory.cleanup()

    def test_status_and_pause_are_local_and_validate_arguments(self):
        response=self.fetch('/api/service')
        self.assertEqual(response.code,200)
        self.assertTrue(json.loads(response.body)['running'])
        self.assertEqual(self.fetch('/api/service',headers={'Origin':'https://example.com'}).code,403)
        def post(body,headers=None):
            return self.fetch('/api/service',method='POST',body=json.dumps(body),headers=headers or {'Content-Type':'application/json'})
        self.assertEqual(post({'action':'service.connection','args':{'enabled':'false'}}).code,400)
        self.assertEqual(post({'action':'service.connection','args':None}).code,400)
        self.assertEqual(post({'action':'service.connection','args':{'enabled':False}},headers={'Origin':'https://example.com'}).code,403)
        self.assertEqual(post({'action':'service.connection','args':{'enabled':False}}).code,200)
        self.assertFalse(json.loads(self.fetch('/api/service').body)['model_enabled'])


class HtmlCacheTests(AsyncHTTPTestCase):
    def get_app(self):
        self.directory=tempfile.TemporaryDirectory()
        self.index=Path(self.directory.name)/'index.html'
        self.index.write_text('<script src="first.js"></script>')
        return web.Application([(r'/(.*)',StaticHandler,{'path':self.directory.name,'default_filename':'index.html'})])

    def tearDown(self):
        super().tearDown()
        self.directory.cleanup()

    def test_root_html_is_never_cached_across_frontend_rebuilds(self):
        initial=self.fetch('/')
        self.assertEqual(initial.headers['Cache-Control'],'no-store')
        self.assertNotIn('Etag',initial.headers)
        self.index.write_text('<script src="second.js"></script>')
        rebuilt=self.fetch('/',headers={'If-Modified-Since':'Wed, 21 Oct 2099 07:28:00 GMT','If-None-Match':'"old"'})
        self.assertEqual(rebuilt.code,200)
        self.assertIn(b'second.js',rebuilt.body)
        self.assertEqual(self.fetch('/index.html').headers['Cache-Control'],'no-store')
