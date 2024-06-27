import websockets
import json
async def injector_js(ws_url,payload):
    async with websockets.connect(ws_url) as websocket:
        await websocket.send(json.dumps(payload))
        response =await websocket.recv()
        result = json.loads(response)['result']['result']['value']
        #print(result)
        return result 
    

javscritpString = open("./test file/test.js","r",encoding="UTF-8").read()

payload={
    'id' : 1,
    'method':'Runtime.evaluate',
    'params':{'expression':f'''{javscritpString}'''}
}

domPayload = {
    'id' : 2,
    'method':'Runtime.evaluate',
    'params':{'expression':f'''document.querySelectorAll('input')[0].value'''}
}
getFileNamePayload = {
    'id' : 3,
    'method':'Runtime.evaluate',
    'params':{'expression':f'''document.querySelector('#left-sidebar > plasticity-filename > div > span').textContent'''}
}

selectObjectPayload ={
    
}


def event_payload(commandStr:str):
    string = f'''
    var existingPointerEvent = new Event("{commandStr}");
    targetElement.dispatchEvent(existingPointerEvent);
    '''
    return string