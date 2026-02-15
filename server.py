#!/usr/bin/env python3
import os
import json
from aiohttp import web
import logging
from curl_cffi.requests import AsyncSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CORS 中间件
@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        response = web.Response()
    else:
        response = await handler(request)
    
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-URL, X-API-Key, X-Server-ID, X-Proxy-URL'
    return response

def get_headers(request):
    api_key = request.headers.get('X-API-Key', '')
    return {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

def get_base_url(request):
    api_url = request.headers.get('X-API-URL', '').rstrip('/')
    server_id = request.headers.get('X-Server-ID', '')
    return f"{api_url}/{server_id}/files"

def get_proxy_url(request):
    return request.headers.get('X-Proxy-URL', '').strip() or None

async def index(request):
    return web.FileResponse('./static/index.html')

async def list_files(request):
    api_url = request.headers.get('X-API-URL', '')
    server_id = request.headers.get('X-Server-ID', '')
    api_key = request.headers.get('X-API-Key', '')
    
    if not api_url or not server_id or not api_key:
        return web.json_response({'error': '请先配置 API 地址、Server ID 和 API Key'}, status=400)
    
    directory = request.query.get('directory', '/')
    proxy = get_proxy_url(request)
    try:
        async with AsyncSession(impersonate="chrome", proxy=proxy) as session:
            url = f"{get_base_url(request)}/list"
            resp = await session.get(url, params={'directory': directory}, headers=get_headers(request))
            if resp.status_code == 200:
                return web.json_response(resp.json())
            else:
                text = resp.text
                if 'Cloudflare' in text or 'Just a moment' in text:
                    return web.json_response({'error': '检测到 Cloudflare 防护，请配置代理'}, status=403)
                try:
                    err_data = resp.json()
                    err_msg = err_data.get('errors', [{}])[0].get('detail', text[:200])
                except:
                    err_msg = text[:200]
                return web.json_response({'error': f'API 错误 ({resp.status_code}): {err_msg}'}, status=resp.status_code)
    except Exception as e:
        logger.exception("list_files error")
        return web.json_response({'error': str(e)}, status=500)

async def get_file_contents(request):
    file_path = request.query.get('file', '')
    proxy = get_proxy_url(request)
    try:
        async with AsyncSession(impersonate="chrome", proxy=proxy) as session:
            url = f"{get_base_url(request)}/contents"
            resp = await session.get(url, params={'file': file_path}, headers=get_headers(request))
            if resp.status_code == 200:
                content = resp.text
                try:
                    data = json.loads(content)
                    if isinstance(data, dict) and data.get('type') == 'Buffer' and 'data' in data:
                        content = bytes(data['data']).decode('utf-8')
                    elif isinstance(data, str):
                        content = data
                except:
                    pass
                return web.Response(text=content, content_type='text/plain')
            else:
                try:
                    err_data = resp.json()
                    err_msg = err_data.get('errors', [{}])[0].get('detail', resp.text[:200])
                except:
                    err_msg = resp.text[:200]
                return web.json_response({'error': err_msg}, status=resp.status_code)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def write_file(request):
    file_path = request.query.get('file', '')
    content = await request.read()
    proxy = get_proxy_url(request)
    try:
        async with AsyncSession(impersonate="chrome", proxy=proxy) as session:
            url = f"{get_base_url(request)}/write"
            headers = get_headers(request)
            headers.pop('Content-Type', None)
            resp = await session.post(url, params={'file': file_path}, data=content, headers=headers)
            if resp.status_code in [200, 204]:
                return web.json_response({'status': 'ok'})
            else:
                return web.json_response({'error': resp.text}, status=resp.status_code)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def delete_files(request):
    data = await request.json()
    proxy = get_proxy_url(request)
    try:
        async with AsyncSession(impersonate="chrome", proxy=proxy) as session:
            url = f"{get_base_url(request)}/delete"
            resp = await session.post(url, json=data, headers=get_headers(request))
            if resp.status_code in [200, 204]:
                return web.json_response({'status': 'ok'})
            else:
                return web.json_response({'error': resp.text}, status=resp.status_code)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def rename_file(request):
    data = await request.json()
    proxy = get_proxy_url(request)
    try:
        async with AsyncSession(impersonate="chrome", proxy=proxy) as session:
            url = f"{get_base_url(request)}/rename"
            resp = await session.put(url, json=data, headers=get_headers(request))
            if resp.status_code in [200, 204]:
                return web.json_response({'status': 'ok'})
            else:
                return web.json_response({'error': resp.text}, status=resp.status_code)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def create_folder(request):
    data = await request.json()
    proxy = get_proxy_url(request)
    try:
        async with AsyncSession(impersonate="chrome", proxy=proxy) as session:
            url = f"{get_base_url(request)}/create-folder"
            resp = await session.post(url, json=data, headers=get_headers(request))
            if resp.status_code in [200, 204]:
                return web.json_response({'status': 'ok'})
            else:
                return web.json_response({'error': resp.text}, status=resp.status_code)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def download_file(request):
    file_path = request.query.get('file', '')
    proxy = get_proxy_url(request)
    try:
        async with AsyncSession(impersonate="chrome", proxy=proxy) as session:
            url = f"{get_base_url(request)}/download"
            resp = await session.get(url, params={'file': file_path}, headers=get_headers(request))
            if resp.status_code == 200:
                return web.json_response(resp.json())
            else:
                return web.json_response({'error': resp.text}, status=resp.status_code)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def get_upload_url(request):
    proxy = get_proxy_url(request)
    try:
        async with AsyncSession(impersonate="chrome", proxy=proxy) as session:
            url = f"{get_base_url(request)}/upload"
            resp = await session.get(url, headers=get_headers(request))
            if resp.status_code == 200:
                return web.json_response(resp.json())
            else:
                return web.json_response({'error': resp.text}, status=resp.status_code)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def proxy_upload(request):
    """代理上传文件到 Wings 服务器"""
    directory = request.query.get('directory', '/')
    proxy = get_proxy_url(request)
    try:
        async with AsyncSession(impersonate="chrome", proxy=proxy) as session:
            # 获取上传 URL
            url = f"{get_base_url(request)}/upload"
            resp = await session.get(url, headers=get_headers(request))
            if resp.status_code != 200:
                return web.json_response({'error': f'获取上传地址失败: {resp.text}'}, status=resp.status_code)
            
            upload_url = resp.json().get('attributes', {}).get('url', '')
            if not upload_url:
                return web.json_response({'error': '无法获取上传地址'}, status=500)
            
            # 读取上传的文件
            reader = await request.multipart()
            files = []
            async for part in reader:
                if part.filename:
                    content = await part.read()
                    files.append(('files', (part.filename, content)))
            
            # 上传到 Wings
            full_url = f"{upload_url}&directory={directory}"
            resp = await session.post(full_url, files=files)
            if resp.status_code in [200, 204]:
                return web.json_response({'status': 'ok'})
            else:
                return web.json_response({'error': f'上传失败: {resp.text}'}, status=resp.status_code)
    except Exception as e:
        logger.exception("proxy_upload error")
        return web.json_response({'error': str(e)}, status=500)

# ==================== 电源控制 ====================

async def power_action(request):
    """电源操作: start, stop, restart, kill"""
    data = await request.json()
    action = data.get('signal', '')
    if action not in ['start', 'stop', 'restart', 'kill']:
        return web.json_response({'error': '无效的操作，支持: start, stop, restart, kill'}, status=400)
    
    proxy = get_proxy_url(request)
    try:
        async with AsyncSession(impersonate="chrome", proxy=proxy) as session:
            url = f"{get_base_url(request).replace('/files', '')}/power"
            resp = await session.post(url, json={'signal': action}, headers=get_headers(request))
            if resp.status_code in [200, 204]:
                return web.json_response({'status': 'ok', 'action': action})
            else:
                return web.json_response({'error': resp.text}, status=resp.status_code)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def get_server_resources(request):
    """获取服务器资源使用情况"""
    proxy = get_proxy_url(request)
    try:
        async with AsyncSession(impersonate="chrome", proxy=proxy) as session:
            url = f"{get_base_url(request).replace('/files', '')}/resources"
            resp = await session.get(url, headers=get_headers(request))
            if resp.status_code == 200:
                return web.json_response(resp.json())
            else:
                return web.json_response({'error': resp.text}, status=resp.status_code)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def send_command(request):
    """发送控制台命令"""
    data = await request.json()
    command = data.get('command', '')
    if not command:
        return web.json_response({'error': '命令不能为空'}, status=400)
    
    proxy = get_proxy_url(request)
    try:
        async with AsyncSession(impersonate="chrome", proxy=proxy) as session:
            url = f"{get_base_url(request).replace('/files', '')}/command"
            resp = await session.post(url, json={'command': command}, headers=get_headers(request))
            if resp.status_code in [200, 204]:
                return web.json_response({'status': 'ok'})
            else:
                return web.json_response({'error': resp.text}, status=resp.status_code)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def compress_files(request):
    data = await request.json()
    proxy = get_proxy_url(request)
    try:
        async with AsyncSession(impersonate="chrome", proxy=proxy) as session:
            url = f"{get_base_url(request)}/compress"
            resp = await session.post(url, json=data, headers=get_headers(request))
            if resp.status_code in [200, 204]:
                return web.json_response(resp.json())
            else:
                return web.json_response({'error': resp.text}, status=resp.status_code)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def decompress_file(request):
    data = await request.json()
    proxy = get_proxy_url(request)
    try:
        async with AsyncSession(impersonate="chrome", proxy=proxy) as session:
            url = f"{get_base_url(request)}/decompress"
            resp = await session.post(url, json=data, headers=get_headers(request))
            if resp.status_code in [200, 204]:
                return web.json_response({'status': 'ok'})
            else:
                return web.json_response({'error': resp.text}, status=resp.status_code)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

app = web.Application(client_max_size=1024**3, middlewares=[cors_middleware])
app.router.add_get('/', index)
app.router.add_route('OPTIONS', '/api/files/{tail:.*}', lambda r: web.Response())
app.router.add_get('/api/files/list', list_files)
app.router.add_get('/api/files/contents', get_file_contents)
app.router.add_post('/api/files/write', write_file)
app.router.add_post('/api/files/delete', delete_files)
app.router.add_post('/api/files/rename', rename_file)
app.router.add_post('/api/files/create-folder', create_folder)
app.router.add_get('/api/files/download', download_file)
app.router.add_get('/api/files/upload', get_upload_url)
app.router.add_post('/api/files/proxy-upload', proxy_upload)
app.router.add_post('/api/power', power_action)
app.router.add_get('/api/resources', get_server_resources)
app.router.add_post('/api/command', send_command)
app.router.add_post('/api/files/compress', compress_files)
app.router.add_post('/api/files/decompress', decompress_file)
app.router.add_route('OPTIONS', '/api/{tail:.*}', lambda r: web.Response())
app.router.add_static('/static', './static')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    logger.info(f"Starting server on port {port}")
    web.run_app(app, host='0.0.0.0', port=port)
