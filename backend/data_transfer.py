"""Reviewed, transactional transfers. Uploaded archives are never extracted."""
import hashlib
import io
import json
import re
import shutil
import sqlite3
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from .asset_library import AssetLibrary

MAX_UPLOAD = 512 * 1024 * 1024
MAX_EXPANDED = 2 * 1024 * 1024 * 1024
MAX_ITEMS = 10000
ASSET_COLUMNS = 'id,name,category,tags,note,created_at,source_version,digest,model,preview,archived,updated_at,library_id,folder_id,kind,insert_mode,recipe_json'.split(',')


def fingerprint(db):
    data = [list(map(tuple, db.execute(query))) for query in (
        'SELECT id,name,category,tags,note,created_at,updated_at,digest,archived,library_id,folder_id,kind,insert_mode,recipe_json FROM assets ORDER BY id',
        'SELECT * FROM libraries ORDER BY id', 'SELECT * FROM folders ORDER BY id')]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False).encode()).hexdigest()


def insert_asset(db, row, source=None):
    db.execute('INSERT OR REPLACE INTO assets (' + ','.join(ASSET_COLUMNS) + ') VALUES (' + ','.join('?' for _ in ASSET_COLUMNS) + ')',
               [row[column] for column in ASSET_COLUMNS])
    if source is not None:
        with source.connect() as stage:
            calibration = stage.execute('SELECT report FROM native_model_layouts WHERE digest=?', (row['digest'],)).fetchone()
        if calibration:
            db.execute('INSERT OR REPLACE INTO native_model_layouts VALUES (?,?)', (row['digest'],calibration[0]))


class DataTransfer:
    def __init__(self, library):
        self.library = library
        self.plans = {}

    def discard(self, token):
        plan = self.plans.pop(token, None)
        if plan:
            plan['temporary'].cleanup()

    def expire(self):
        for token, plan in list(self.plans.items()):
            if time.monotonic() - plan['created'] > 600:
                self.discard(token)

    def backup(self):
        output = tempfile.SpooledTemporaryFile(max_size=8*1024*1024, mode='w+b')
        try:
            with tempfile.TemporaryDirectory() as directory:
                snapshot = AssetLibrary(directory)
                with self.library.connect() as source, snapshot.connect() as target:
                    source.backup(target)
                with snapshot.connect() as db:
                    rows = list(db.execute('SELECT id,archived,created_at,updated_at FROM assets ORDER BY id'))
                    libraries = [dict(row) for row in db.execute('SELECT * FROM libraries')]
                    folders = [dict(row) for row in db.execute('SELECT * FROM folders')]
                    total = db.execute('SELECT coalesce(sum(length(model)+coalesce(length(preview),0)),0) FROM assets').fetchone()[0]
                if len(rows) > MAX_ITEMS or total > MAX_EXPANDED:
                    raise ValueError('整库备份支持最多 10000 个组件和 2 GB 模型与图片数据')
                manifest = {'format':'plasticity-asset-library-backup','version':1,
                            'created_at':datetime.now(timezone.utc).isoformat(),
                            'libraries':libraries,'folders':folders,'assets':[]}
                with zipfile.ZipFile(output, 'w', zipfile.ZIP_STORED) as archive:
                    for row in rows:
                        name = 'components/' + row['id'] + '.patasset'
                        archive.writestr(name, snapshot.export(row['id']))
                        manifest['assets'].append(dict(row) | {'file':name})
                    archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False))
                if output.tell() > MAX_UPLOAD:
                    raise ValueError('备份压缩包超过 512 MB，请拆分组件导出或减少库数据后重试')
                output.seek(0)
                return output
        except BaseException:
            output.close()
            raise

    @staticmethod
    def archive(payload):
        archive = zipfile.ZipFile(io.BytesIO(payload))
        entries = archive.infolist()
        if len(entries) > MAX_ITEMS + 1 or len({entry.filename for entry in entries}) != len(entries):
            archive.close()
            raise ValueError('ZIP 包包含过多或重复文件')
        if any(entry.flag_bits & 1 or entry.file_size > 70*1024*1024 for entry in entries) or sum(entry.file_size for entry in entries) > MAX_EXPANDED:
            archive.close()
            raise ValueError('ZIP 包不能加密，展开大小不能超过 2 GB')
        return archive

    @staticmethod
    def organization(stage, manifest):
        libraries, folders = manifest.get('libraries'), manifest.get('folders')
        if not isinstance(libraries,list) or not isinstance(folders,list) or len(libraries)+len(folders)>MAX_ITEMS:
            raise ValueError('备份组织结构无效')
        def identifier(value):
            return isinstance(value,str) and (value=='default' or re.fullmatch('[a-f0-9]{32}',value))
        library_ids, folder_map = set(), {}
        for row in libraries:
            if not isinstance(row,dict) or not identifier(row.get('id')) or row['id'] in library_ids:
                raise ValueError('备份资产库 ID 无效或重复')
            AssetLibrary.validate_fields(row)
            library_ids.add(row['id'])
        if 'default' not in library_ids:
            raise ValueError('备份缺少默认库')
        for row in folders:
            if not isinstance(row,dict) or not identifier(row.get('id')) or row['id'] in folder_map or row.get('library_id') not in library_ids:
                raise ValueError('备份分组无效')
            AssetLibrary.validate_fields(row)
            folder_map[row['id']] = row
        for row in folders:
            visited = {row['id']}
            parent = row.get('parent_id')
            while parent is not None:
                if parent in visited or parent not in folder_map or folder_map[parent]['library_id']!=row['library_id']:
                    raise ValueError('备份分组父级无效或存在循环')
                visited.add(parent)
                parent = folder_map[parent].get('parent_id')
        with stage.connect() as db:
            db.execute('DELETE FROM libraries')
            for row in libraries:
                db.execute('INSERT INTO libraries VALUES (?,?,?)', (row['id'],row['name'],row.get('created_at','')))
            for row in folders:
                db.execute('INSERT INTO folders VALUES (?,?,?,?,?)', (row['id'],row['library_id'],row.get('parent_id'),row['name'],row.get('created_at','')))

    def preview(self, files, kind='import', library_id='default', folder_id=None):
        self.expire()
        if kind not in ('import','restore') or not files or len(files)>MAX_ITEMS or sum(len(body) for _,body in files)>MAX_UPLOAD:
            raise ValueError('请选择有效文件，上传合计不超过 512 MB')
        if len(self.plans)>=4:
            raise ValueError('待确认任务过多，请先完成或取消已有任务')
        temporary = tempfile.TemporaryDirectory()
        stage = AssetLibrary(temporary.name)
        items, total = [], 0
        try:
            if kind=='import':
                self.library.validate_location(library_id, folder_id)
            def component(name, payload, backup_row=None):
                nonlocal total
                if len(payload)>70*1024*1024 or len(items)>=MAX_ITEMS:
                    raise ValueError('导入内容超过 10000 个组件或 2 GB')
                # Existing package validation checks model hashes, recipes and JPEGs.
                location = ('default',None)
                if backup_row:
                    with zipfile.ZipFile(io.BytesIO(payload)) as inner:
                        meta = json.loads(inner.read('manifest.json'))
                    if meta.get('id')!=backup_row.get('id'):
                        raise ValueError('备份组件 ID 不匹配')
                    location = (meta.get('library_id','default'),meta.get('folder_id'))
                saved = stage.import_package(payload,*location)
                row = dict(stage.get(saved['id']))
                total += len(row['model']) + len(row['preview'] or b'')
                if total>MAX_EXPANDED:
                    raise ValueError('展开的模型与图片超过 2 GB')
                if backup_row:
                    if not re.fullmatch('[a-f0-9]{32}',str(backup_row.get('id',''))) or backup_row.get('archived') not in (0,1):
                        raise ValueError('备份组件状态无效')
                    row.update({key:backup_row[key] for key in ('id','archived','created_at','updated_at')})
                    if not all(isinstance(row[key],str) and len(row[key])<100 for key in ('created_at','updated_at')):
                        raise ValueError('备份时间无效')
                    with stage.connect() as db:
                        db.execute('DELETE FROM assets WHERE id=?',(saved['id'],))
                        if db.execute('SELECT 1 FROM assets WHERE id=?',(row['id'],)).fetchone():
                            raise ValueError('备份组件 ID 重复')
                        insert_asset(db,row)
                else:
                    row.update(library_id=library_id,folder_id=folder_id)
                size=len(row.pop('model'));row.pop('preview')
                items.append({'index':len(items),'file':name,'row':row,'bytes':size,
                              'stage_id':row['id'] if backup_row else saved['id']})
            if kind=='restore':
                if len(files)!=1:
                    raise ValueError('恢复时请选择一个整库备份 ZIP')
                with self.archive(files[0][1]) as archive:
                    if archive.getinfo('manifest.json').file_size>8*1024*1024:
                        raise ValueError('备份清单过大')
                    manifest=json.loads(archive.read('manifest.json'))
                    if manifest.get('format')!='plasticity-asset-library-backup' or manifest.get('version')!=1:
                        raise ValueError('这是组件分享包，请在组件库导入；恢复需要整库备份')
                    self.organization(stage,manifest)
                    rows=manifest.get('assets')
                    if not isinstance(rows,list) or len(rows)>MAX_ITEMS:
                        raise ValueError('备份组件清单无效')
                    expected=['manifest.json']+[row['file'] for row in rows]
                    if len(set(expected))!=len(expected) or set(expected)!=set(archive.namelist()):
                        raise ValueError('备份文件清单不匹配')
                    for row in rows:
                        component(row['file'],archive.read(row['file']),row)
            else:
                for name,payload in files:
                    if name.lower().endswith('.patasset'):
                        component(name,payload)
                    elif name.lower().endswith('.zip'):
                        with self.archive(payload) as archive:
                            entries=[entry for entry in archive.infolist() if not entry.is_dir()]
                            if not entries or any(not entry.filename.lower().endswith('.patasset') for entry in entries):
                                raise ValueError('组件 ZIP 只能包含 .patasset 文件；整库备份请在控制中心恢复')
                            for entry in entries:
                                component(entry.filename,archive.read(entry))
                    else:
                        raise ValueError('请选择 .patasset 或组件 ZIP')
            with self.library.connect() as db:
                stamp=fingerprint(db)
                existing=list(db.execute('SELECT id,name,digest,updated_at FROM assets WHERE library_id=? AND folder_id IS ?',(library_id,folder_id)))
            seen=set()
            for item in items:
                row=item['row']
                matches=[entry for entry in existing if entry['digest']==row['digest'] or entry['name']==row['name']]
                item['matches']=[dict(entry) for entry in matches]
                item['duplicate']=row['digest'] in seen
                seen.add(row['digest'])
            token=uuid.uuid4().hex
            self.plans[token]={'temporary':temporary,'stage':stage,'items':items,'stamp':stamp,'kind':kind,'created':time.monotonic()}
            return {'token':token,'kind':kind,'count':len(items),'libraries':stage.libraries() if kind=='restore' else [],
                    'folders':len(manifest['folders']) if kind=='restore' else 0,
                    'items':[{'index':item['index'],'file':item['file'],'name':item['row']['name'],'bytes':item['bytes'],
                              'category':item['row']['category'],'matches':item['matches'],'duplicate':item['duplicate'],
                              'conflict':'identical' if any(match['digest']==item['row']['digest'] for match in item['matches']) else 'name' if item['matches'] else None} for item in items]}
        except (zipfile.BadZipFile,KeyError,TypeError,AttributeError,json.JSONDecodeError,UnicodeError,RuntimeError,sqlite3.Error) as exc:
            temporary.cleanup()
            raise ValueError('无效的组件或备份包：'+str(exc)) from exc
        except BaseException:
            temporary.cleanup()
            raise

    def commit(self, token, choices=None, confirm_restore=False):
        self.expire()
        plan=self.plans.get(token)
        if not plan:
            raise ValueError('预览已过期，请重新选择文件')
        if plan['kind']=='restore' and confirm_restore is not True:
            raise ValueError('请先确认整库替换')
        if plan['kind']=='import' and (not isinstance(choices,list) or len(choices)!=len(plan['items'])):
            raise ValueError('请为每个组件选择导入方式')
        rollback=None
        # BEGIN IMMEDIATE makes fingerprint validation and all writes one transaction.
        with self.library.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if fingerprint(db)!=plan['stamp']:
                raise ValueError('组件库在预览后已变化，请重新预览以确认冲突')
            if plan['kind']=='restore':
                # Back up the committed current database using a separate read connection.
                output=self.backup()
                try:
                    directory=self.library.root.parent/'.runtime'/'library-backups'
                    directory.mkdir(parents=True,exist_ok=True)
                    rollback=directory/('before-restore-'+uuid.uuid4().hex+'.zip')
                    with rollback.open('wb') as file:
                        shutil.copyfileobj(output,file)
                finally:
                    output.close()
                for table in ('assets','geometry_cache','folders','libraries','native_formats','native_model_layouts'):
                    db.execute('DELETE FROM '+table)
                with plan['stage'].connect() as stage:
                    for table,columns in [('libraries','id,name,created_at'),('folders','id,library_id,parent_id,name,created_at')]:
                        for row in stage.execute('SELECT '+columns+' FROM '+table):
                            db.execute('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in row)+')',tuple(row))
                for item in plan['items']:
                    insert_asset(db,dict(plan['stage'].get(item['stage_id'])) | item['row'],plan['stage'])
                counts={'imported':len(plan['items']),'skipped':0,'overwritten':0}
            else:
                counts={'imported':0,'skipped':0,'overwritten':0}
                used=set()
                for item,choice in zip(plan['items'],choices):
                    if not isinstance(choice,dict) or choice.get('mode') not in ('skip','copy','overwrite'):
                        raise ValueError('无效的冲突处理方式')
                    mode=choice['mode']
                    if mode=='skip':
                        counts['skipped']+=1
                        continue
                    row=dict(plan['stage'].get(item['stage_id'])) | item['row']
                    if mode=='overwrite':
                        target=choice.get('target_id')
                        if target not in [entry['id'] for entry in item['matches']] or target in used:
                            raise ValueError('请选择唯一且已在预览中显示的覆盖目标')
                        used.add(target)
                        row['id']=target
                        row['created_at']=db.execute('SELECT created_at FROM assets WHERE id=?',(target,)).fetchone()[0]
                        counts['overwritten']+=1
                    else:
                        row['id']=uuid.uuid4().hex
                        original=row['name'];number=2
                        while db.execute('SELECT 1 FROM assets WHERE library_id=? AND folder_id IS ? AND name=?',(row['library_id'],row['folder_id'],row['name'])).fetchone():
                            suffix=f' ({number})';row['name']=original[:120-len(suffix)]+suffix;number+=1
                        counts['imported']+=1
                    row['updated_at']=datetime.now(timezone.utc).isoformat()
                    insert_asset(db,row,plan['stage'])
        self.discard(token)
        return counts | {'rollback_backup':str(rollback) if rollback else None}
