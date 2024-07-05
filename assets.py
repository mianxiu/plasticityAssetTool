#!/usr/bin/env python

import asyncio
import cdp_payload

injector_js = cdp_payload.injector_js


ws = "ws://127.0.0.1:9223/devtools/page/D1F330B6426643C50C7912FBC0ABAAC7"



#filename = asyncio.run(injector_js(ws,cdp_payload.getFileNamePayload))


png = asyncio.run(injector_js(ws,cdp_payload.screenshot_payload))
print(filename)