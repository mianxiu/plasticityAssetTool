"""Per-window native command jobs; model payloads never touch the OS clipboard."""
import asyncio
import base64
import binascii
import time
import uuid
from model_clipboard import validate_model, MAX_BYTES


class NativeTransport:
    def __init__(self):
        self.workers = {}
        self.jobs = {}

    def connected_targets(self):
        return [key for key, value in self.workers.items() if time.monotonic()-value['seen'] < 5]

    def worker(self, target, token, result=None, capabilities=None):
        if not isinstance(target,str) or not target.startswith('hwnd:') or not target[5:].isdigit() or not isinstance(token,str) or len(token)!=36:
            raise ValueError('无效的模型工作连接')
        now=time.monotonic()
        self.workers={key:value for key,value in self.workers.items() if now-value['seen'] < 30}
        previous=self.workers.get(target)
        if previous and previous['token']!=token and now-previous['seen'] < 5:
            raise ValueError('目标窗口已有模型连接')
        if target not in self.workers and len(self.workers)>=64:
            raise ValueError('模型连接过多')
        self.workers[target]={'seen':now,'token':token,'capabilities':capabilities if isinstance(capabilities,list) else []}
        if isinstance(result,dict):
            job=self.jobs.get(result.get('id'))
            if job and job.get('token')==token and job['target']==target and not job['future'].done():
                try:
                    if result.get('error'):
                        message = str(result['error']).splitlines()[0]
                        if message.startswith('Error: '): message = message[7:]
                        raise ValueError(message[:300])
                    value=result.get('value')
                    if job['action']=='capture':
                        encoded=value.get('model') if isinstance(value,dict) else None
                        if not isinstance(encoded,str) or len(encoded)>MAX_BYTES*4//3+4:
                            raise ValueError('原生模型数据无效')
                        try:
                            value=validate_model(base64.b64decode(encoded,validate=True))
                        except (binascii.Error,ValueError) as exc:
                            raise ValueError('原生模型数据无效') from exc
                    elif not isinstance(value,dict) or value.get('started') is not True:
                        raise ValueError('原生置入没有启动')
                    job['future'].set_result(value)
                except ValueError as error:
                    job['future'].set_exception(error)
        for job_id,job in self.jobs.items():
            if job['target']==target and not job['sent'] and not job['future'].done():
                job['sent']=True
                job['token']=token
                return {'id':job_id,'action':job['action'],**job['payload']}
        return None

    async def request(self, target, action, model=None, placement=True, insert_mode="new-body"):
        if target not in self.connected_targets():
            raise ValueError('目标窗口的原生模型插件未连接，请重新打开已安装插件的 Plasticity')
        if action not in ('capture','insert'):
            raise ValueError('未知的原生模型操作')
        if any(job['target']==target for job in self.jobs.values()):
            raise ValueError('目标窗口正在处理组件，请稍后重试')
        payload={}
        if action=='insert':
            if insert_mode not in ('new-body','union','difference','intersection'):
                raise ValueError('无效的默认置入模式')
            if not placement and insert_mode != 'new-body':
                raise ValueError('布尔模式需要使用定位置入')
            if insert_mode != 'new-body' and 'boolean-placement-v1' not in self.workers[target]['capabilities']:
                raise ValueError('目标窗口尚未加载布尔置入插件，请重新打开 Plasticity')
            payload={'model':base64.b64encode(validate_model(model)).decode(),'placement':bool(placement),'insert_mode':insert_mode}
        future=asyncio.get_running_loop().create_future()
        job_id=uuid.uuid4().hex
        self.jobs[job_id]={'target':target,'action':action,'payload':payload,'future':future,'sent':False}
        try:
            return await asyncio.wait_for(asyncio.shield(future),10)
        except asyncio.TimeoutError as exc:
            raise ValueError('原生模型操作超时；请检查目标窗口的状态后再操作，勿重复置入') from exc
        finally:
            self.jobs.pop(job_id,None)
            if not future.done(): future.cancel()
