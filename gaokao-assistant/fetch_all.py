"""
批量爬取大学详细数据
从 discovered_schools.json 读取学校列表，逐个获取 Q&A 详情，合并到 data.json
"""
import json
import urllib.request
import urllib.parse
import time
import re
import os
import sys

# 强制 UTF-8 输出
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')
DISCOVERED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'discovered_schools.json')
BASE_URL = 'https://eyunb666.03-06.cn/api.php'

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_chinese_university(name):
    """过滤：只保留中国大陆高校"""
    # 必须包含中文字符
    if not re.search(r'[一-鿿]', name):
        return False
    # 排除纯英文名（虽然有中文后缀但主体是英文）
    if re.match(r'^[A-Za-z]', name) and not re.match(r'^[一-鿿]', name):
        return False
    # 排除日文
    if re.search(r'[぀-ゟ゠-ヿ]', name):
        return False
    return True

def clean_name(name):
    """清理学校名称"""
    # 去除前缀垃圾字符
    name = re.sub(r'^[\.\-\s]+', '', name)
    # 去除尾部的校区/学院后缀（保留主校名）
    # 但如果本身就是学院则保留
    return name.strip()

def fetch_detail(name, retries=2):
    """获取学校详情"""
    url = f"{BASE_URL}?name={urllib.parse.quote(name)}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0'
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if 'error' in data:
                    return None
                return data
        except Exception as e:
            if attempt == retries - 1:
                return None
            time.sleep(2)
    return None

def main():
    # 加载已发现的学校
    discovered = load_json(DISCOVERED_FILE)
    print(f'发现学校总数: {len(discovered)}')

    # 加载现有数据
    existing_data = load_json(DATA_FILE)
    existing_names = {u['name'] for u in existing_data.get('universities', [])}
    print(f'已有详细数据: {len(existing_names)} 所')

    # 过滤并清理
    candidates = []
    for item in discovered:
        raw_name = item['name']
        if not is_chinese_university(raw_name):
            continue
        name = clean_name(raw_name)
        if name and name not in existing_names:
            candidates.append(name)

    # 去重
    candidates = list(set(candidates))
    print(f'待爬取: {len(candidates)} 所大学')
    print('-' * 50)

    # 批量爬取
    new_universities = []
    success = 0
    empty = 0
    failed = 0

    for i, name in enumerate(candidates):
        print(f'[{i+1}/{len(candidates)}] {name} ... ', end='', flush=True)

        detail = fetch_detail(name)
        if detail is None:
            print('❌ 无数据')
            failed += 1
        elif not detail.get('qa') or len(detail['qa']) == 0:
            print('📭 无Q&A')
            empty += 1
            # 仍然添加（占位）
            new_universities.append({
                'name': name,
                'qa': [],
                'user_replies': []
            })
        else:
            qa_count = len(detail.get('qa', []))
            print(f'✅ {qa_count}个问题')
            new_universities.append({
                'name': name,
                'qa': detail.get('qa', []),
                'user_replies': detail.get('user_replies', [])
            })
            success += 1

        # 礼貌延迟（避免被ban）
        time.sleep(0.6)

    print('-' * 50)
    print(f'成功: {success} | 空数据: {empty} | 失败: {failed}')

    # 合并到现有数据
    existing_data['universities'].extend(new_universities)

    # 更新热搜列表（取浏览量最高的前15所）
    all_hot = []
    for u in existing_data['universities']:
        all_hot.append({
            'school_name': u['name'],
            'views': str(len(u.get('qa', [])) * 100 + len(u.get('user_replies', [])) * 10 + 100)  # 模拟浏览量
        })

    # 按浏览量排序
    all_hot.sort(key=lambda x: int(x['views']), reverse=True)
    existing_data['hot'] = all_hot[:15]

    # 保存
    save_json(DATA_FILE, existing_data)
    print(f'\n✅ data.json 已更新！共计 {len(existing_data["universities"])} 所大学')

if __name__ == '__main__':
    main()
