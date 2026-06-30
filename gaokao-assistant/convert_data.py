"""
将 CollegesChat 原始问卷数据 (results_desensitized.csv) 转换为 data.json 格式
数据来源: https://github.com/CollegesChat/university-information
"""
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ===== 路径配置 =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, 'gaokao_data_collegeschat', 'questionnaires', 'results_desensitized.csv')
COLLEGES_FILE = os.path.join(BASE_DIR, 'gaokao_data_collegeschat', 'questionnaires', 'colleges.csv')
ALIAS_FILE = os.path.join(BASE_DIR, 'gaokao_data_collegeschat', 'questionnaires', 'alias.txt')
BLACKLIST_FILE = os.path.join(BASE_DIR, 'gaokao_data_collegeschat', 'questionnaires', 'blacklist.txt')
WHITELIST_FILE = os.path.join(BASE_DIR, 'gaokao_data_collegeschat', 'questionnaires', 'whitelist.txt')
DATA_FILE = os.path.join(BASE_DIR, 'data.json')

# ===== 25 个标准问题 =====
QUESTIONS = [
    '宿舍是上床下桌吗？',
    '教室和宿舍有没有空调？',
    '有独立卫浴吗？没有独立浴室的话，澡堂离宿舍多远？',
    '有早自习、晚自习吗？',
    '有晨跑吗？',
    '每学期跑步打卡的要求是多少公里，可以骑车吗？',
    '寒暑假放多久，每年小学期有多长？',
    '学校允许点外卖吗，取外卖的地方离宿舍楼多远？',
    '学校交通便利吗，有地铁吗，在市区吗，不在的话进城要多久？',
    '宿舍楼有洗衣机吗？',
    '校园网怎么样？',
    '每天断电断网吗，几点开始断？',
    '食堂价格贵吗，会吃出异物吗？',
    '洗澡热水供应时间？',
    '校园内可以骑电瓶车吗，电池在哪能充电？',
    '宿舍限电情况？',
    '通宵自习有去处吗？',
    '大一能带电脑吗？',
    '学校里面用什么卡，饭堂怎样消费？',
    '学校会给学生发银行卡吗？',
    '学校的超市怎么样？',
    '学校的收发快递政策怎么样？',
    '学校里面的共享单车数目与种类如何？',
    '现阶段学校的门禁情况如何？',
    '宿舍晚上查寝吗，封寝吗，晚归能回去吗？',
]

NAME_PREPROCESS = re.compile(r'[\(\)（）【】#]')
NORMAL_NAME_MATCHER = re.compile(r'大学|学院|学校')


def load_colleges():
    """加载 colleges.csv，建立 校名关键词→省份 映射"""
    colleges = {}
    with open(COLLEGES_FILE, 'r', encoding='utf-8') as f:
        csv_reader = csv.reader(f)
        for row in csv_reader:
            if len(row) >= 2:
                province, college = row
                clean = NAME_PREPROCESS.sub('', college).replace(' ', '')
                colleges[clean] = province
    return colleges


def load_alias():
    """加载 alias.txt，建立 别名→标准名 映射"""
    alias_map = {}
    with open(ALIAS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('🚮')
            if len(parts) >= 2:
                canonical = parts[0].strip()
                for alias in parts[1:]:
                    alias_clean = NAME_PREPROCESS.sub('', alias).strip()
                    canonical_clean = NAME_PREPROCESS.sub('', canonical).strip()
                    alias_map[alias_clean] = canonical_clean
    return alias_map


def load_blacklist():
    """加载黑名单"""
    blacklist = set()
    with open(BLACKLIST_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            name = line.strip()
            if name:
                blacklist.add(name)
    return blacklist


def find_province(name, colleges):
    """根据校名匹配省份"""
    sorted_keys = sorted(colleges.keys(), key=len, reverse=True)
    best_prov = ''
    best_len = 0
    for key in sorted_keys:
        if key in name and len(key) > best_len:
            best_prov = colleges[key]
            best_len = len(key)
    return best_prov


def is_chinese_university(name):
    """判断是否是中国大陆高校"""
    # 必须有中文
    if not re.search(r'[一-鿿]', name):
        return False
    # 排除日文
    if re.search(r'[぀-ゟ゠-ヿ]', name):
        return False
    # 排除纯英文但有中文字符的
    if re.match(r'^[A-Za-z]', name) and not re.match(r'^[一-鿿]', name):
        return False
    return True


def is_middle_school(name):
    """判断是否可能是中学（非大学）"""
    if name.endswith('中') or '中学' in name or name.endswith('高'):
        return True
    return False


def normalize_name(name):
    """清理校名"""
    # 去除括号内容
    name = NAME_PREPROCESS.sub('', name)
    # 去除多余空格
    name = re.sub(r'\s+', '', name)
    # 去除方括号内容
    name = re.sub(r'\[.*?\]', '', name)
    return name.strip()


def extract_universities():
    """从 CSV 提取所有大学的 Q&A 数据"""
    alias_map = load_alias()
    blacklist = load_blacklist()

    # 使用 defaultdict 按校名分组
    # 结构: {name: {answer_id: {q_index: answer_text}}}
    universities = defaultdict(lambda: {
        'answers': [defaultdict(list) for _ in range(len(QUESTIONS))],
        'additional': defaultdict(str)
    })

    total_rows = 0
    skipped_no_name = 0
    skipped_non_chinese = 0
    skipped_blacklisted = 0
    skipped_middle = 0

    print('正在读取 CSV 文件...')
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        csv_reader = csv.reader(f)
        next(csv_reader)  # 跳过 header

        for row in csv_reader:
            total_rows += 1
            if len(row) < 6:
                continue

            # 按照 main.py 的解析逻辑
            aid = row[0].strip()
            # row[1] = 来源 (skip)
            # row[2] = anonymous flag
            # row[3] = email
            # row[4] = show_email
            raw_name = row[5].strip() if len(row) > 5 else ''

            if not raw_name or not aid:
                skipped_no_name += 1
                continue

            # 清理校名
            name = normalize_name(raw_name)

            # 应用别名映射
            name = alias_map.get(name, name)

            if not name:
                skipped_no_name += 1
                continue

            # 过滤
            if not is_chinese_university(name):
                skipped_non_chinese += 1
                continue
            if name in blacklist:
                skipped_blacklisted += 1
                continue
            if is_middle_school(name) and NORMAL_NAME_MATCHER.search(name) is None:
                skipped_middle += 1
                continue

            # 提取 25 个问题的回答
            answers_start = 6
            for q_idx in range(len(QUESTIONS)):
                col_idx = answers_start + q_idx
                if col_idx < len(row):
                    ans = row[col_idx].strip()
                    if ans and ans != '[DESENSITIZED]':
                        universities[name]['answers'][q_idx][aid].append(ans)

            # 提取自由补充
            if len(row) >= 10:
                additional = row[-9].strip()
                if additional and additional != '[DESENSITIZED]' and len(additional) > 0:
                    universities[name]['additional'][aid] = additional

            if total_rows % 10000 == 0:
                print(f'  已处理 {total_rows} 行...')

    print(f'\nCSV 解析完成:')
    print(f'  总行数: {total_rows}')
    print(f'  跳过(无名称): {skipped_no_name}')
    print(f'  跳过(非中国高校): {skipped_non_chinese}')
    print(f'  跳过(黑名单): {skipped_blacklisted}')
    print(f'  跳过(中学): {skipped_middle}')
    print(f'  有效大学: {len(universities)}')

    return universities


def build_data_json(universities):
    """构建 data.json 格式"""
    colleges_map = load_colleges()

    uni_list = []
    province_counts = defaultdict(int)

    for name, data in sorted(universities.items()):
        # 构建 Q&A
        qa_list = []
        total_answers = 0

        for q_idx in range(len(QUESTIONS)):
            answers_dict = data['answers'][q_idx]
            if not answers_dict:
                continue

            # 按 answer_id 排序，格式化为 "A{id}: {content}"
            formatted_answers = []
            for aid in sorted(answers_dict.keys(), key=lambda x: int(x) if x.isdigit() else 0):
                for ans_text in answers_dict[aid]:
                    formatted_answers.append(f'A{aid}: {ans_text}')
                    total_answers += 1

            if formatted_answers:
                qa_list.append({
                    'q': QUESTIONS[q_idx],
                    'a': formatted_answers
                })

        # 如果没有任何有效回答，跳过
        if not qa_list:
            continue

        # 省份
        province = find_province(name, colleges_map)
        if province:
            province_counts[province] += 1

        # 构建大学条目
        uni_entry = {
            'name': name,
            'province': province,
            'qa': qa_list,
        }

        # 添加自由补充
        if data['additional']:
            user_replies = []
            for aid in sorted(data['additional'].keys(), key=lambda x: int(x) if x.isdigit() else 0):
                user_replies.append({
                    'user_content': f'A{aid}: {data["additional"][aid]}',
                    'time': ''
                })
            if user_replies:
                uni_entry['user_replies'] = user_replies

        uni_list.append(uni_entry)

    # 按回答数量排序
    uni_list.sort(key=lambda u: sum(len(qa['a']) for qa in u['qa']), reverse=True)

    # 生成热搜列表（前15所，按浏览量）
    hot_list = []
    for u in uni_list[:15]:
        views = sum(len(qa['a']) for qa in u['qa'])
        hot_list.append({
            'school_name': u['name'],
            'views': str(views * 100)
        })

    # 构建完整数据
    data = {
        'notice': f'欢迎使用高考志愿大学助手！🏫 这里汇集了全国 {len(uni_list)} 所高校的真实生活体验，由在校学长学姐匿名贡献。数据仅供参考，实际情况可能因校区、专业不同而有差异。',
        'hot': hot_list,
        'universities': uni_list
    }

    return data, province_counts


def merge_with_existing(new_data):
    """合并新数据到已有的 data.json（保留已有数据中可能更详细的内容）"""
    if not os.path.exists(DATA_FILE):
        return new_data

    print('\n正在加载已有 data.json...')
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        existing = json.load(f)

    existing_map = {u['name']: u for u in existing.get('universities', [])}
    new_map = {u['name']: u for u in new_data['universities']}

    merged = []

    # 保留已有大学中不在新数据中的（如果有的话）
    for name, uni in existing_map.items():
        if name not in new_map:
            merged.append(uni)
            continue

        # 已有数据中有，新数据中也有 → 合并（以已有数据为主，补充新数据中多的回答）
        new_uni = new_map[name]
        existing_qa_map = {qa['q']: qa for qa in uni.get('qa', [])}

        for new_qa in new_uni.get('qa', []):
            if new_qa['q'] not in existing_qa_map:
                # 已有数据中没有这个问题，添加
                uni.setdefault('qa', []).append(new_qa)
            else:
                # 已有数据中有这个问题，合并回答（去重）
                existing_a = set(existing_qa_map[new_qa['q']]['a'])
                for a in new_qa['a']:
                    if a not in existing_a:
                        existing_qa_map[new_qa['q']]['a'].append(a)

        # 合并 user_replies
        if 'user_replies' in new_uni:
            existing_replies = uni.get('user_replies', [])
            existing_contents = {r.get('user_content', '') for r in existing_replies}
            for r in new_uni['user_replies']:
                if r.get('user_content', '') not in existing_contents:
                    existing_replies.append(r)
            if existing_replies:
                uni['user_replies'] = existing_replies

        # 确保有 province
        if not uni.get('province') and new_uni.get('province'):
            uni['province'] = new_uni['province']

        merged.append(uni)

    # 添加只有新数据中才有的大学
    for name, uni in new_map.items():
        if name not in existing_map:
            merged.append(uni)

    # 按总回答数排序
    merged.sort(key=lambda u: sum(len(qa.get('a', [])) for qa in u.get('qa', [])), reverse=True)

    # 更新热搜列表
    hot_list = []
    for u in merged[:15]:
        views = sum(len(qa.get('a', [])) for qa in u.get('qa', []))
        hot_list.append({
            'school_name': u['name'],
            'views': str(views * 100)
        })

    return {
        'notice': new_data['notice'].replace(str(len(new_data['universities'])), str(len(merged))),
        'hot': hot_list,
        'universities': merged
    }


def main():
    print('=' * 60)
    print('  🏫 CollegesChat CSV → data.json 转换工具')
    print('=' * 60)
    print(f'  源文件: {CSV_FILE}')
    print(f'  目标: {DATA_FILE}')
    print()

    # 1. 从 CSV 提取数据
    universities = extract_universities()

    # 2. 构建 data.json 格式
    print('\n正在构建 data.json 格式...')
    new_data, province_counts = build_data_json(universities)
    print(f'  有效大学: {len(new_data["universities"])} 所')
    print(f'  省份分布: {len(province_counts)} 个省')

    # 省份统计
    print('\n省份分布 Top 20:')
    for prov, count in sorted(province_counts.items(), key=lambda x: -x[1])[:20]:
        print(f'  {prov}: {count} 所')

    # 3. 与已有数据合并
    final_data = merge_with_existing(new_data)
    print(f'\n合并后总计: {len(final_data["universities"])} 所大学')

    # 4. 保存
    print(f'\n正在保存到 {DATA_FILE}...')
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    # 文件大小
    size_mb = os.path.getsize(DATA_FILE) / (1024 * 1024)
    print(f'✅ 保存完成！文件大小: {size_mb:.1f} MB')

    # 5. 统计
    total_qa = sum(len(u.get('qa', [])) for u in final_data['universities'])
    total_ans = sum(sum(len(qa.get('a', [])) for qa in u.get('qa', [])) for u in final_data['universities'])
    with_province = sum(1 for u in final_data['universities'] if u.get('province'))
    print(f'\n📊 数据统计:')
    print(f'  大学总数: {len(final_data["universities"])}')
    print(f'  有省份标注: {with_province}')
    print(f'  总 Q&A 条目: {total_qa}')
    print(f'  总回答数: {total_ans}')
    print(f'  平均每校回答数: {total_ans / len(final_data["universities"]):.1f}')


if __name__ == '__main__':
    main()
