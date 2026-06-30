"""
高考志愿大学助手 - 后端服务器
纯 Python 实现，无需额外依赖。运行: python server.py
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# 修复 Windows 终端编码问题
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')
CORRECTION_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'correction_log.txt')
PORT = 8080


# ===== 内存缓存（避免每次请求都加载 68MB JSON） =====
_cached_data = None
_cached_data_mtime = 0


def load_data():
    """读取数据文件（带内存缓存）"""
    global _cached_data, _cached_data_mtime
    if not os.path.exists(DATA_FILE):
        return {'notice': '数据文件不存在', 'hot': [], 'universities': []}
    mtime = os.path.getmtime(DATA_FILE)
    if _cached_data is None or mtime != _cached_data_mtime:
        print(f'[缓存] 加载数据文件 ({os.path.getsize(DATA_FILE)/1024/1024:.0f}MB)...')
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            _cached_data = json.load(f)
        _cached_data_mtime = mtime
        # 构建搜索索引
        _build_indices(_cached_data)
    return _cached_data


# ===== 搜索索引 =====
_name_index = {}       # 校名关键词 → [大学名]
_question_index = {}   # 问题关键词 → [(大学名, 问题, 回答预览)]
_province_index = {}   # 省份 → [大学名]


def _build_indices(data):
    """构建搜索索引以加速查询"""
    global _name_index, _question_index, _province_index
    _name_index.clear()
    _question_index.clear()
    _province_index.clear()

    for u in data.get('universities', []):
        name = u['name']
        province = u.get('province', '')
        qa_list = u.get('qa', [])

        # 省份索引
        if province:
            _province_index.setdefault(province, []).append(name)

        # 校名索引（按单字索引）
        for char in name:
            _name_index.setdefault(char, set()).add(name)

        # 问题索引
        for qa in qa_list:
            for word in qa['q']:
                _question_index.setdefault(word, set()).add(
                    (name, qa['q'], '；'.join(qa['a'][:3]))
                )


def save_data(data):
    """保存数据文件并更新缓存"""
    global _cached_data, _cached_data_mtime
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _cached_data = data
    _cached_data_mtime = os.path.getmtime(DATA_FILE)
    _build_indices(data)


def log_correction(old_name, new_name):
    """记录校名纠错日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(CORRECTION_LOG, 'a', encoding='utf-8') as f:
        f.write(f'{timestamp} | 旧名: {old_name} | 新名: {new_name}\n')


def json_response(handler, data, status=200):
    """发送 JSON 响应"""
    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def serve_static(handler, path):
    """提供静态文件"""
    # 映射路径到文件
    if path == '/' or path == '/index.html':
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
        content_type = 'text/html; charset=utf-8'
    elif path == '/data.json':
        # 不允许直接访问数据文件
        json_response(handler, {'error': '禁止直接访问'}, 403)
        return
    else:
        json_response(handler, {'error': 'Not Found'}, 404)
        return

    if not os.path.exists(file_path):
        json_response(handler, {'error': '文件不存在'}, 404)
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    body = content.encode('utf-8')
    handler.send_response(200)
    handler.send_header('Content-Type', content_type)
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class APIHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        # API 路由
        if path == '/api.php' or path == '/api':
            self.handle_api_get(params)
        elif path == '/' or path.endswith('.html') or path.endswith('.css') or path.endswith('.js'):
            serve_static(self, path)
        else:
            # 尝试作为静态文件
            serve_static(self, path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == '/api.php' or path == '/api':
            # 读取 POST body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            params = urllib.parse.parse_qs(body)
            self.handle_api_post(params)
        else:
            json_response(self, {'error': 'Not Found'}, 404)

    def handle_api_get(self, params):
        data = load_data()

        # 首页数据
        if 'get_home' in params:
            # 收集省份及数量
            province_count = {}
            for u in data.get('universities', []):
                p = u.get('province', '')
                if p:
                    province_count[p] = province_count.get(p, 0) + 1
            province_list = [{'name': p, 'count': c} for p, c in sorted(province_count.items())]
            json_response(self, {
                'notice': data.get('notice', '欢迎使用！'),
                'hot': data.get('hot', []),
                'provinces': province_list,
                'total': len(data.get('universities', []))
            })
            return

        # 按省份查询（返回该省全部学校，使用索引）
        if 'province' in params:
            prov = params['province'][0].strip()
            results = []
            if prov and prov in _province_index:
                for name in _province_index[prov]:
                    # 从数据中获取 qa_count
                    for u in data.get('universities', []):
                        if u['name'] == name:
                            results.append({
                                'school_name': name,
                                'province': prov,
                                'qa_count': len(u.get('qa', []))
                            })
                            break
            json_response(self, results)
            return

        # 按学校名搜索（使用校名关键词匹配）
        if 'search' in params:
            kw = params['search'][0].strip()
            results = []
            if kw:
                # 尝试用索引加速（单字搜索）
                if len(kw) == 1 and kw in _name_index:
                    candidates = _name_index[kw]
                else:
                    candidates = None

                for u in data.get('universities', []):
                    if candidates is not None and u['name'] not in candidates:
                        continue
                    if kw.lower() in u['name'].lower():
                        results.append({
                            'school_name': u['name'],
                            'province': u.get('province', '')
                        })
            json_response(self, results)
            return

        # 按条件搜索（使用问题索引）
        if 'search_q' in params:
            kw = params['search_q'][0].strip()
            results = []
            seen = set()
            if kw:
                # 使用索引
                if kw in _question_index:
                    for name, q, preview in _question_index[kw]:
                        if name not in seen:
                            results.append({
                                'school_name': name,
                                'q': q,
                                'a': preview,
                                'province': ''
                            })
                            seen.add(name)
                else:
                    # 回退到全文搜索
                    for u in data.get('universities', []):
                        for qa in u.get('qa', []):
                            if kw.lower() in qa['q'].lower():
                                preview = '；'.join(qa['a'][:3])
                                results.append({
                                    'school_name': u['name'],
                                    'q': qa['q'],
                                    'a': preview,
                                    'province': u.get('province', '')
                                })
                                break
            json_response(self, results)
            return

        # 获取学校详情
        if 'name' in params:
            name = params['name'][0].strip()
            found = None
            for u in data.get('universities', []):
                if u['name'] == name:
                    # 初始化浏览量（从热搜列表中获取初始值）
                    if 'views' not in u:
                        init_views = 0
                        for h in data.get('hot', []):
                            if h['school_name'] == name:
                                try:
                                    init_views = int(h['views'])
                                except (ValueError, TypeError):
                                    init_views = 0
                                break
                        u['views'] = init_views
                    # 增加浏览量
                    u['views'] += 1
                    save_data(data)
                    found = u
                    break

            if found:
                json_response(self, found)
            else:
                json_response(self, {'error': '未找到该学校的信息'})
            return

        # 无有效参数
        json_response(self, {'error': '请提供有效的查询参数'})

    def handle_api_post(self, params):
        data = load_data()

        # 用户提交补充
        if 'submit_content' in params:
            school_name = params.get('school_name', [''])[0].strip()
            content = params.get('user_content', [''])[0].strip()

            if not school_name or not content:
                json_response(self, {'error': '学校名称和补充内容不能为空'})
                return
            if len(content) > 500:
                json_response(self, {'error': '内容不能超过500字'})
                return

            found = False
            for u in data.get('universities', []):
                if u['name'] == school_name:
                    if 'user_replies' not in u:
                        u['user_replies'] = []
                    u['user_replies'].append({
                        'user_content': content,
                        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    found = True
                    break

            if found:
                save_data(data)
                json_response(self, {'status': 'ok', 'msg': '✅ 提交成功！感谢你的贡献，内容将在审核后显示。'})
            else:
                json_response(self, {'error': '未找到该学校，请检查学校名称是否正确'})
            return

        # 校名纠错
        if 'report_error' in params:
            old_name = params.get('old_name', [''])[0].strip()
            new_name = params.get('new_name', [''])[0].strip()

            if not old_name or not new_name:
                json_response(self, {'error': '新旧校名不能为空'})
                return

            log_correction(old_name, new_name)
            json_response(self, {
                'status': 'ok',
                'msg': f'✅ 感谢反馈！我们已记录【{old_name}】→【{new_name}】的更正建议，核实后会尽快更新。'
            })
            return

        # AI 问答
        if 'ask_ai' in params:
            school_name = params.get('school_name', [''])[0].strip()
            question = params.get('question', [''])[0].strip()

            if not school_name or not question:
                json_response(self, {'error': '学校名称和问题不能为空'})
                return
            if len(question) > 300:
                json_response(self, {'error': '问题不能超过300字'})
                return

            # 查找学校数据
            school_data = None
            for u in data.get('universities', []):
                if u['name'] == school_name:
                    school_data = u
                    break

            if not school_data:
                json_response(self, {'error': '未找到该学校'})
                return

            # 构建上下文
            qa_text = ''
            for qa in school_data.get('qa', []):
                answers = '；'.join(qa['a'][:5])  # 最多5条回答
                qa_text += f'Q: {qa["q"]}\nA: {answers}\n\n'

            if not qa_text:
                qa_text = '该校暂无生活数据。'

            system_prompt = f"""你是【{school_name}】的校园生活AI助手。你只能回答关于这所学校的问题。

以下是本站收录的该校真实校友反馈数据，请基于这些数据回答问题：

{qa_text}

重要规则：
1. 只能回答关于【{school_name}】的问题
2. 如果用户问其他学校或其他话题，回复："⚠️ 我只能回答关于【{school_name}】的问题哦～如果你想了解其他学校，请返回首页搜索该校并进入其详情页提问。"
3. 回答时要引用数据来源（如"根据校友反馈..."）
4. 如果数据中没有相关信息，诚实告知，不要编造
5. 回答简洁有条理，适当使用emoji和换行
6. 回答末尾不要添加任何免责声明（前端会自动附加）"""

            # 调用 DeepSeek API
            api_key = os.environ.get('DEEPSEEK_API_KEY')
            if not api_key:
                json_response(self, {'error': 'AI功能未配置，请联系管理员设置 API Key'})
                return

            try:
                req_body = json.dumps({
                    'model': 'deepseek-chat',
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': question}
                    ],
                    'temperature': 0.7,
                    'max_tokens': 800,
                    'stream': False
                }).encode('utf-8')

                api_req = urllib.request.Request(
                    'https://api.deepseek.com/chat/completions',
                    data=req_body,
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {api_key}'
                    }
                )

                with urllib.request.urlopen(api_req, timeout=30) as resp:
                    result = json.loads(resp.read().decode('utf-8'))
                    answer = result['choices'][0]['message']['content']
                    json_response(self, {'status': 'ok', 'answer': answer})

            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8') if e.fp else ''
                print(f'DeepSeek API error: {e.code} {error_body}')
                json_response(self, {'error': f'AI接口调用失败（{e.code}），请稍后重试'})
            except Exception as e:
                print(f'AI request failed: {e}')
                json_response(self, {'error': 'AI接口连接超时，请稍后重试'})

            return

        json_response(self, {'error': '无效的请求'})

    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f'[{datetime.now().strftime("%H:%M:%S")}] {args[0]}')


def main():
    print('=' * 50)
    print('  🏫 高考志愿大学助手 - 服务器启动')
    print('=' * 50)
    print(f'  地址: http://localhost:{PORT}')
    print(f'  数据: {DATA_FILE}')
    print(f'  按 Ctrl+C 停止服务器')
    print('=' * 50)

    server = HTTPServer(('0.0.0.0', PORT), APIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务器已停止。')
        server.server_close()


if __name__ == '__main__':
    main()
