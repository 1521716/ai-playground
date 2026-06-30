"""
批量为大学数据添加官网链接
使用 pypinyin 将中文校名转拼音，按标准模式生成 .edu.cn 网址
"""
import json, os, re, sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')

# ===== 手工维护的知名大学官网映射（确保准确性） =====
MANUAL_WEBSITES = {
    '北京大学': 'https://www.pku.edu.cn',
    '清华大学': 'https://www.tsinghua.edu.cn',
    '上海交通大学': 'https://www.sjtu.edu.cn',
    '复旦大学': 'https://www.fudan.edu.cn',
    '浙江大学': 'https://www.zju.edu.cn',
    '南京大学': 'https://www.nju.edu.cn',
    '武汉大学': 'https://www.whu.edu.cn',
    '华中科技大学': 'https://www.hust.edu.cn',
    '中国科学技术大学': 'https://www.ustc.edu.cn',
    '中国人民大学': 'https://www.ruc.edu.cn',
    '中山大学': 'https://www.sysu.edu.cn',
    '同济大学': 'https://www.tongji.edu.cn',
    '南开大学': 'https://www.nankai.edu.cn',
    '天津大学': 'https://www.tju.edu.cn',
    '哈尔滨工业大学': 'https://www.hit.edu.cn',
    '西安交通大学': 'https://www.xjtu.edu.cn',
    '北京航空航天大学': 'https://www.buaa.edu.cn',
    '北京理工大学': 'https://www.bit.edu.cn',
    '北京师范大学': 'https://www.bnu.edu.cn',
    '中国农业大学': 'https://www.cau.edu.cn',
    '华东师范大学': 'https://www.ecnu.edu.cn',
    '厦门大学': 'https://www.xmu.edu.cn',
    '山东大学': 'https://www.sdu.edu.cn',
    '中国海洋大学': 'https://www.ouc.edu.cn',
    '四川大学': 'https://www.scu.edu.cn',
    '湖南大学': 'https://www.hnu.edu.cn',
    '中南大学': 'https://www.csu.edu.cn',
    '东南大学': 'https://www.seu.edu.cn',
    '华南理工大学': 'https://www.scut.edu.cn',
    '大连理工大学': 'https://www.dlut.edu.cn',
    '西北工业大学': 'https://www.nwpu.edu.cn',
    '吉林大学': 'https://www.jlu.edu.cn',
    '重庆大学': 'https://www.cqu.edu.cn',
    '兰州大学': 'https://www.lzu.edu.cn',
    '东北大学': 'https://www.neu.edu.cn',
    '郑州大学': 'https://www.zzu.edu.cn',
    '云南大学': 'https://www.ynu.edu.cn',
    '上海大学': 'https://www.shu.edu.cn',
    '深圳大学': 'https://www.szu.edu.cn',
    '中国政法大学': 'https://www.cupl.edu.cn',
    '中央财经大学': 'https://www.cufe.edu.cn',
    '对外经济贸易大学': 'https://www.uibe.edu.cn',
    '上海财经大学': 'https://www.sufe.edu.cn',
    '北京邮电大学': 'https://www.bupt.edu.cn',
    '华东政法大学': 'https://www.ecupl.edu.cn',
    '中南财经政法大学': 'https://www.zuel.edu.cn',
    '北京外国语大学': 'https://www.bfsu.edu.cn',
    '上海外国语大学': 'https://www.shisu.edu.cn',
    '中国传媒大学': 'https://www.cuc.edu.cn',
    '北京体育大学': 'https://www.bsu.edu.cn',
    '中央民族大学': 'https://www.muc.edu.cn',
    '上海科技大学': 'https://www.shanghaitech.edu.cn',
    '南京航空航天大学': 'https://www.nuaa.edu.cn',
    '南京理工大学': 'https://www.njust.edu.cn',
    '北京交通大学': 'https://www.bjtu.edu.cn',
    '北京科技大学': 'https://www.ustb.edu.cn',
    '北京化工大学': 'https://www.buct.edu.cn',
    '北京林业大学': 'https://www.bjfu.edu.cn',
    '北京中医药大学': 'https://www.bucm.edu.cn',
    '华北电力大学': 'https://www.ncepu.edu.cn',
    '河海大学': 'https://www.hhu.edu.cn',
    '江南大学': 'https://www.jiangnan.edu.cn',
    '南京农业大学': 'https://www.njau.edu.cn',
    '中国矿业大学': 'https://www.cumt.edu.cn',
    '中国石油大学': 'https://www.upc.edu.cn',
    '中国地质大学': 'https://www.cug.edu.cn',
    '华中农业大学': 'https://www.hzau.edu.cn',
    '华中师范大学': 'https://www.ccnu.edu.cn',
    '东北师范大学': 'https://www.nenu.edu.cn',
    '西南大学': 'https://www.swu.edu.cn',
    '西南交通大学': 'https://www.swjtu.edu.cn',
    '西北农林科技大学': 'https://www.nwafu.edu.cn',
    '西安电子科技大学': 'https://www.xidian.edu.cn',
    '长安大学': 'https://www.chd.edu.cn',
    '陕西师范大学': 'https://www.snnu.edu.cn',
    '西北大学': 'https://www.nwu.edu.cn',
    '合肥工业大学': 'https://www.hfut.edu.cn',
    '东北林业大学': 'https://www.nefu.edu.cn',
    '东北农业大学': 'https://www.neau.edu.cn',
}

# 无需官网的学校关键词
NO_WEBSITE_KEYWORDS = [
    '部队', '军队', '解放军', '军事', '国防', '航天工程',
    '信息支援', '军委', '武警', '火箭军', '战略支援',
]

# 校区变体 → 主校（提取主校名）
CAMPUS_SUFFIXES = [
    '校区', '学院路', '本部', '海淀', '昌平', '闵行', '徐汇',
    '良乡', '沙河', '汉中门', '仙林', '天目湖', '将军路',
    '枫林', '广兰', '抚州', '净月', '莞城', '湖光', '海滨',
    '阳江', '寸金学院', '涉外学院', '翰林学院',
    '大学城', '新校区', '西校区', '东校区', '南校区', '北校区',
    '中校区', '基础学院', '专业学院', '技术大学', '技术学院',
    'B区', '注：', '（', '(',
]


def clean_to_main_school(name):
    """提取主校名"""
    # 先看看手工映射里有没有
    for full_name in MANUAL_WEBSITES:
        if name.startswith(full_name) or full_name.startswith(name):
            return full_name

    # 去除校区后缀
    cleaned = name
    for suffix in CAMPUS_SUFFIXES:
        idx = cleaned.find(suffix)
        if idx > 0:
            cleaned = cleaned[:idx]
            break

    return cleaned.strip()


def should_skip_website(name):
    """判断是否应该跳过生成官网"""
    for kw in NO_WEBSITE_KEYWORDS:
        if kw in name:
            return True
    return False


def generate_website_pinyin(name):
    """使用 pypinyin 生成可能的官网网址"""
    try:
        from pypinyin import pinyin, Style
        # 转为拼音首字母或全拼
        py_list = pinyin(name, style=Style.NORMAL)
        # 全拼
        full_py = ''.join([p[0] for p in py_list])
        # 首字母
        initials = ''.join([p[0][0] for p in py_list])

        # 常见模式
        candidates = [
            f'https://www.{full_py}.edu.cn',
        ]

        return candidates[0]
    except Exception:
        return ''


def main():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    universities = data['universities']
    success_manual = 0
    success_pinyin = 0
    skipped = 0
    failed = 0

    for u in universities:
        name = u['name']
        if 'website' in u and u['website']:
            continue  # 已有官网，跳过

        if should_skip_website(name):
            u['website'] = ''
            skipped += 1
            continue

        # 1. 先尝试手工映射（包括校区匹配到主校）
        main_name = clean_to_main_school(name)
        if main_name in MANUAL_WEBSITES:
            u['website'] = MANUAL_WEBSITES[main_name]
            success_manual += 1
            continue

        # 2. 尝试手工模糊匹配
        matched = False
        for known_name, url in MANUAL_WEBSITES.items():
            if name.startswith(known_name) or known_name.startswith(name):
                u['website'] = url
                success_manual += 1
                matched = True
                break
        if matched:
            continue

        # 3. pypinyin 自动生成
        website = generate_website_pinyin(name)
        if website:
            u['website'] = website
            success_pinyin += 1
        else:
            u['website'] = ''
            failed += 1

    # 保存
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'官网链接生成完成！')
    print(f'  手工映射: {success_manual} 所')
    print(f'  拼音生成: {success_pinyin} 所')
    print(f'  跳过(军队等): {skipped} 所')
    print(f'  失败: {failed} 所')
    print(f'  总计: {len(universities)} 所')

    # 展示几个示例
    print('\n示例:')
    for u in universities[:5]:
        print(f'  {u["name"]} → {u.get("website", "(无)")}')
    # 找几个有官网的
    count = 0
    for u in universities:
        if u.get('website'):
            print(f'  {u["name"]} → {u["website"]}')
            count += 1
            if count >= 5:
                break


if __name__ == '__main__':
    main()
