# -*- coding: utf-8 -*-
"""
A股个股归一化走势图生成器
输入: 股票代码或名称
输出: HTML 点线图（收盘价 + PE TTM + 申万二级行业指数，全部归一化到首日=1.0）

用法:
  python generate_stock_chart.py 600519
  python generate_stock_chart.py 贵州茅台
  python generate_stock_chart.py 000001 --days 180
  python generate_stock_chart.py 600519 --output /path/to/output.html
"""
import sys
import os
import re
import time
import json
import argparse
import ssl
import urllib3

# === SSL patch (some AKShare data sources have cert issues) ===
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context
try:
    import requests
    _old_request = requests.Session.request
    def _patched_request(self, *args, **kwargs):
        kwargs['verify'] = False
        return _old_request(self, *args, **kwargs)
    requests.Session.request = _patched_request
except ImportError:
    pass

# === Auto-install dependencies if missing ===
def _ensure_deps():
    import subprocess
    for pkg in ['akshare', 'pandas', 'urllib3']:
        try:
            __import__(pkg)
        except ImportError:
            print(f"  Installing {pkg}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg, '-q'])

_ensure_deps()

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta


# === SW industry_code (first 4 digits) -> (SW index code, SW index name) ===
# Built from stock_industry_clf_hist_sw + index_realtime_sw cross-referencing
# with well-known stocks. Covers ~60 most common second-level industries.
SW_INDUSTRY_MAP = {
    # === 农林牧渔 (11) ===
    '1101': ('801012', '农产品加工'),
    '1102': ('801038', '农化制品'),  # 农化制品 might be under 化工
    '1103': ('801014', '饲料'),
    '1104': ('801015', '渔业'),
    '1105': ('801016', '种植业'),
    '1106': ('801016', '种植业'),
    '1107': ('801017', '养殖业'),
    '1108': ('801018', '动物保健Ⅱ'),
    # === 基础化工 (23) ===
    '2301': ('801032', '化学纤维'),
    '2302': ('801033', '化学原料'),
    '2303': ('801034', '化学制品'),
    '2304': ('801044', '普钢'),  # 钢铁
    '2305': ('801045', '特钢Ⅱ'),
    # === 有色金属 (24) ===
    '2401': ('801051', '金属新材料'),
    '2402': ('801053', '贵金属'),
    '2403': ('801055', '工业金属'),
    '2404': ('801054', '小金属'),
    '2405': ('801056', '能源金属'),
    # === 电子 (27) ===
    '2701': ('801081', '半导体'),
    '2702': ('801082', '其他电子Ⅱ'),
    '2703': ('801084', '光学光电子'),
    '2704': ('801083', '元件'),
    '2705': ('801085', '消费电子'),
    '2706': ('801086', '电子化学品Ⅱ'),
    # === 汽车 (28) ===
    '2804': ('801093', '汽车零部件'),
    '2805': ('801095', '乘用车'),
    '2806': ('801096', '商用车'),
    '2807': ('801092', '汽车服务'),
    # === 家用电器 (33) ===
    '3301': ('801111', '白色家电'),
    '3302': ('801112', '黑色家电'),
    '3303': ('801113', '小家电'),
    '3304': ('801114', '厨卫电器'),
    '3305': ('801115', '照明设备Ⅱ'),
    '3306': ('801116', '家电零部件Ⅱ'),
    # === 食品饮料 (34) ===
    '3401': ('801124', '食品加工'),
    '3403': ('801126', '非白酒'),
    '3404': ('801128', '休闲食品'),
    '3405': ('801125', '白酒Ⅱ'),
    '3406': ('801129', '调味发酵品Ⅱ'),
    '3407': ('801127', '饮料乳品'),
    # === 纺织服饰 (35) ===
    '3501': ('801131', '纺织制造'),
    '3502': ('801132', '服装家纺'),
    '3503': ('801133', '饰品'),
    # === 轻工制造 (36) ===
    '3601': ('801141', '包装印刷'),
    '3602': ('801142', '家居用品'),
    '3603': ('801143', '造纸'),
    '3604': ('801145', '文娱用品'),
    # === 医药生物 (37) ===
    '3701': ('801151', '化学制药'),
    '3702': ('801155', '中药Ⅱ'),
    '3703': ('801152', '生物制品'),
    '3704': ('801153', '医疗器械'),
    '3705': ('801154', '医药商业'),
    '3706': ('801156', '医疗服务'),
    # === 美容护理 (38) ===
    '3801': ('801981', '个护用品'),
    '3802': ('801982', '化妆品'),
    # === 传媒 (40) ===
    '4001': ('801764', '游戏Ⅱ'),
    '4002': ('801765', '广告营销'),
    '4003': ('801766', '影视院线'),
    '4004': ('801767', '数字媒体'),
    '4005': ('801769', '出版'),
    # === 通信 (41) ===
    '4101': ('801102', '通信设备'),
    '4102': ('801223', '通信服务'),
    '7302': ('801102', '通信设备'),  # 亿联网络等新分类代码
    # === 计算机 (71/42) ===
    '7101': ('801101', '计算机设备'),
    '7103': ('801103', 'IT服务Ⅱ'),
    '7104': ('801104', '软件开发'),
    # === 银行 (48) ===
    '4802': ('801782', '国有大型银行Ⅱ'),
    '4803': ('801783', '股份制银行Ⅱ'),
    '4804': ('801784', '城商行Ⅱ'),
    '4805': ('801785', '农商行Ⅱ'),
    # === 非银金融 (49) ===
    '4901': ('801193', '证券Ⅱ'),
    '4902': ('801194', '保险Ⅱ'),
    '4903': ('801191', '多元金融'),
    # === 房地产 (43) ===
    '4301': ('801181', '房地产开发'),
    '4302': ('801183', '房地产服务'),
    # === 交通运输 (42/44) ===
    '4210': ('801991', '航空机场'),
    '4211': ('801992', '航运港口'),
    '4401': ('801179', '铁路公路'),
    '4403': ('801178', '物流'),
    # === 商贸零售 (45) ===
    '4501': ('801203', '一般零售'),
    '4502': ('801202', '贸易Ⅱ'),
    '4507': ('801204', '专业连锁Ⅱ'),
    '4508': ('801206', '互联网电商'),
    # === 社会服务 (46) ===
    '4601': ('801219', '酒店餐饮'),
    '4602': ('801993', '旅游及景区'),
    '4603': ('801218', '专业服务'),
    '4604': ('801994', '教育'),
    # === 建筑材料 (61) ===
    '6101': ('801711', '水泥'),
    '6102': ('801712', '玻璃玻纤'),
    '6103': ('801713', '装修建材'),
    # === 建筑装饰 (62) ===
    '6201': ('801721', '房屋建设Ⅱ'),
    '6202': ('801722', '装修装饰Ⅱ'),
    '6203': ('801723', '基础建设'),
    '6204': ('801724', '专业工程'),
    '6205': ('801726', '工程咨询服务Ⅱ'),
    # === 电力设备 (63) ===
    '6302': ('801731', '电机Ⅱ'),
    '6303': ('801733', '其他电源设备Ⅱ'),
    '6305': ('801735', '光伏设备'),
    '6306': ('801736', '风电设备'),
    '6307': ('801737', '电池'),
    '6308': ('801738', '电网设备'),
    # === 机械设备 (64) ===
    '6402': ('801072', '通用设备'),
    '6403': ('801074', '专用设备'),
    '6404': ('801076', '轨交设备Ⅱ'),
    '6406': ('801077', '工程机械'),
    '6407': ('801078', '自动化设备'),
    # === 国防军工 (65) ===
    '6501': ('801741', '航天装备Ⅱ'),
    '6502': ('801742', '航空装备Ⅱ'),
    '6503': ('801743', '地面兵装Ⅱ'),
    '6504': ('801744', '航海装备Ⅱ'),
    '6505': ('801745', '军工电子Ⅱ'),
    # === 公用事业 (66/67) ===
    '6601': ('801161', '电力'),
    '6602': ('801163', '燃气Ⅱ'),
    # === 煤炭 (75) ===
    '7501': ('801951', '煤炭开采'),
    '7502': ('801952', '焦炭Ⅱ'),
    # === 石油石化 (75) ===
    '7503': ('801963', '炼化及贸易'),
    '7504': ('801962', '油服工程'),
    # === 环保 (77) ===
    '7701': ('801971', '环境治理'),
    '7702': ('801972', '环保设备Ⅱ'),
    # === 综合 (80) ===
    '8001': ('801231', '综合Ⅱ'),
}


def resolve_stock_code(input_str):
    """将股票名称或代码统一解析为 (code, sina_prefix, em_prefix)"""
    input_str = input_str.strip()

    # 纯数字代码
    if re.match(r'^\d{6}$', input_str):
        code = input_str
        if code.startswith('6'):
            return code, 'sh', 'SH'
        elif code.startswith(('0', '3')):
            return code, 'sz', 'SZ'
        elif code.startswith(('8', '4')):
            return code, 'bj', 'BJ'
        else:
            return code, 'sh', 'SH'

    # 名称查询: 使用轻量级 stock_info_a_code_name (比 stock_zh_a_spot_em 轻得多)
    print(f"  查询股票名称: {input_str}")
    df_names = ak.stock_info_a_code_name()
    match = df_names[df_names['name'].str.contains(input_str)]
    if match.empty:
        match = df_names[df_names['name'].str.startswith(input_str)]
    if match.empty:
        raise ValueError(f"未找到股票: {input_str}")

    code = str(match.iloc[0]['code'])
    name = match.iloc[0]['name']
    print(f"  匹配到: {name}({code})")

    if code.startswith('6'):
        return code, 'sh', 'SH'
    elif code.startswith(('0', '3')):
        return code, 'sz', 'SZ'
    elif code.startswith(('8', '4')):
        return code, 'bj', 'BJ'
    else:
        return code, 'sh', 'SH'


def get_stock_name(code, em_prefix):
    """获取股票名称"""
    try:
        df = ak.stock_individual_info_em(symbol=code)
        row = df[df['item'] == '股票简称']
        if not row.empty:
            return row.iloc[0]['value']
    except:
        pass
    # Fallback: use stock_info_a_code_name
    try:
        df = ak.stock_info_a_code_name()
        row = df[df['code'] == code]
        if not row.empty:
            return row.iloc[0]['name']
    except:
        pass
    return code


def get_sw_industry(code):
    """
    根据股票代码查询其所属申万二级行业指数。
    返回 (sw_index_code, sw_index_name) 或 None。

    策略1: stock_industry_clf_hist_sw 获取 industry_name → 动态匹配 index_realtime_sw 指数名称
    策略2: 静态映射表 SW_INDUSTRY_MAP (industry_code 前4位 → 指数代码)
    策略3: stock_individual_info_em 获取行业名 → 名称匹配
    策略4: 降级为双线图
    """
    print(f"  查询申万行业归属...")

    # --- 获取所有 SW 二级行业指数列表 (用于名称匹配) ---
    sw_indices = None
    try:
        sw_indices = ak.index_realtime_sw()
        if sw_indices is not None and not sw_indices.empty:
            # 列名可能是中文，统一重命名
            if '指数代码' not in sw_indices.columns:
                sw_indices.columns = ['指数代码', '指数名称', '日期', '开盘', '收盘', '成交量', '成交额', '最高', '最低']
            sw_indices['指数代码'] = sw_indices['指数代码'].astype(str)
            sw_indices['指数名称'] = sw_indices['指数名称'].astype(str)
            print(f"  获取到 {len(sw_indices)} 个申万行业指数")
    except Exception as e:
        print(f"  获取 SW 指数列表失败: {e}")

    def match_sw_index_by_name(industry_name):
        """通过行业名称在 SW 指数列表中匹配对应的指数代码"""
        if sw_indices is None or sw_indices.empty or not industry_name:
            return None

        # 清理名称中的 II/Ⅱ 后缀以增强匹配
        clean_name = industry_name.replace('Ⅱ', '').replace('II', '').replace('Ⅱ', '').strip()
        clean_indices = sw_indices.copy()
        clean_indices['clean_name'] = clean_indices['指数名称'].str.replace('Ⅱ', '').str.replace('II', '').str.strip()

        # 1. 精确匹配
        match = clean_indices[clean_indices['clean_name'] == clean_name]
        if not match.empty:
            return match.iloc[0]['指数代码'], match.iloc[0]['指数名称']

        # 2. 包含匹配 (industry_name 包含在指数名称中, 或反之)
        match = clean_indices[clean_indices['clean_name'].str.contains(clean_name, na=False)]
        if not match.empty:
            return match.iloc[0]['指数代码'], match.iloc[0]['指数名称']

        match = clean_indices[clean_indices['clean_name'].apply(lambda x: clean_name in x if x else False)]
        if not match.empty:
            return match.iloc[0]['指数代码'], match.iloc[0]['指数名称']

        # 3. 反向包含 (指数名称包含在 industry_name 中)
        match = clean_indices[clean_indices['clean_name'].apply(lambda x: x in clean_name if x else False)]
        if not match.empty:
            return match.iloc[0]['指数代码'], match.iloc[0]['指数名称']

        return None

    # === 策略1: stock_industry_clf_hist_sw → 动态名称匹配 ===
    try:
        df = ak.stock_industry_clf_hist_sw()
        df['start_date'] = df['start_date'].astype(str)
        df_latest = df.sort_values('start_date').drop_duplicates('symbol', keep='last')
        rows = df_latest[df_latest['symbol'] == code]
        if not rows.empty:
            industry_code = str(rows.iloc[0]['industry_code'])
            industry_name = str(rows.iloc[0].get('industry_name', ''))
            second_level = industry_code[:4]
            print(f"  行业代码: {industry_code} (二级: {second_level}), 行业名称: {industry_name}")

            # 1a. 先尝试动态名称匹配 (最可靠, 不依赖静态表)
            if industry_name:
                result = match_sw_index_by_name(industry_name)
                if result:
                    print(f"  申万二级行业(名称匹配): {result[1]}({result[0]})")
                    return result
                print(f"  名称匹配未命中, 尝试映射表...")

            # 1b. 映射表兜底
            if second_level in SW_INDUSTRY_MAP:
                sw_code, sw_name = SW_INDUSTRY_MAP[second_level]
                print(f"  申万二级行业(映射表): {sw_name}({sw_code})")
                return sw_code, sw_name
            else:
                print(f"  映射表中也未找到二级代码 {second_level}")
    except Exception as e:
        print(f"  stock_industry_clf_hist_sw 失败: {e}")

    # === 策略2: stock_individual_info_em + 名称匹配 ===
    try:
        df_info = ak.stock_individual_info_em(symbol=code)
        industry_row = df_info[df_info['item'] == '行业']
        if not industry_row.empty:
            industry_name = industry_row.iloc[0]['value']
            print(f"  个股行业(eastmoney): {industry_name}")

            if sw_indices is not None and not sw_indices.empty:
                result = match_sw_index_by_name(industry_name)
                if result:
                    print(f"  申万二级行业(EM匹配): {result[1]}({result[0]})")
                    return result
                print(f"  名称匹配未命中")
    except Exception as e:
        print(f"  stock_individual_info_em 失败: {e}")

    print(f"  ⚠ 无法找到申万行业归属，将跳过行业指数线")
    return None


def retry(func, max_retries=3, delay=5):
    for i in range(max_retries):
        try:
            return func()
        except Exception as e:
            print(f"   Retry {i+1}/{max_retries}: {type(e).__name__}: {e}")
            if i < max_retries - 1:
                time.sleep(delay)
            else:
                raise


def fetch_data(code, em_prefix, sina_prefix, start_date, end_date):
    """获取三组数据: 股价, PE TTM, SW行业指数(可选)"""
    # 1. 股价 (新浪源)
    print("1. 获取股价数据...")
    df_price = retry(lambda: ak.stock_zh_a_daily(
        symbol=f'{sina_prefix}{code}', start_date=start_date, end_date=end_date, adjust='qfq'
    ))
    df_price['日期'] = pd.to_datetime(df_price['date'])
    df_price = df_price[['日期', 'close']].rename(columns={'close': '收盘价'})
    print(f"   OK: {len(df_price)} 行")

    # 2. PE TTM (百度股市通)
    print("2. 获取 PE TTM...")
    time.sleep(2)
    df_pe = retry(lambda: ak.stock_zh_valuation_baidu(
        symbol=code, indicator="市盈率(TTM)", period="近一年"
    ))
    date_col = [c for c in df_pe.columns if '日期' in c or 'date' in c.lower()]
    df_pe['日期'] = pd.to_datetime(df_pe[date_col[0]] if date_col else df_pe.iloc[:, 0])
    pe_col = [c for c in df_pe.columns if '市盈率' in c or 'TTM' in c]
    if pe_col:
        df_pe = df_pe[['日期', pe_col[0]]].rename(columns={pe_col[0]: 'PE_TTM'})
    else:
        df_pe = df_pe[['日期', df_pe.columns[1]]].rename(columns={df_pe.columns[1]: 'PE_TTM'})
    df_pe['PE_TTM'] = pd.to_numeric(df_pe['PE_TTM'], errors='coerce')
    df_pe = df_pe.dropna(subset=['PE_TTM'])
    print(f"   OK: {len(df_pe)} 行")

    # 3. SW 行业指数 (可选)
    print("3. 获取申万行业指数...")
    time.sleep(2)
    sw_result = get_sw_industry(code)

    df_sw = None
    sw_name = None
    if sw_result:
        sw_code, sw_name = sw_result
        time.sleep(2)
        try:
            df_sw = retry(lambda: ak.index_hist_sw(symbol=sw_code, period="day"))
            date_col_sw = [c for c in df_sw.columns if '日期' in c or 'date' in c.lower()]
            df_sw['日期'] = pd.to_datetime(df_sw[date_col_sw[0]] if date_col_sw else df_sw.iloc[:, 0])
            close_col_sw = [c for c in df_sw.columns if '收盘' in c or 'close' in c.lower()]
            if close_col_sw:
                df_sw = df_sw[['日期', close_col_sw[0]]].rename(columns={close_col_sw[0]: '行业指数收盘价'})
            else:
                df_sw = df_sw[['日期', df_sw.columns[1]]].rename(columns={df_sw.columns[1]: '行业指数收盘价'})
            df_sw['行业指数收盘价'] = pd.to_numeric(df_sw['行业指数收盘价'], errors='coerce')
            df_sw = df_sw[(df_sw['日期'] >= start_date) & (df_sw['日期'] <= end_date)]
            print(f"   OK: {len(df_sw)} 行")
        except Exception as e:
            print(f"   ⚠ 获取行业指数历史数据失败: {e}")
            df_sw = None
            sw_name = None

    return df_price, df_pe, df_sw, sw_name


def generate_chart(code, name, df_price, df_pe, df_sw, sw_name, output_path):
    """合并、归一化、生成HTML"""
    has_sw = df_sw is not None and not df_sw.empty

    # 合并
    print("4. 合并数据...")
    df = pd.merge(df_price, df_pe, on='日期', how='outer')
    if has_sw:
        df = pd.merge(df, df_sw, on='日期', how='outer')
    df = df.sort_values('日期').reset_index(drop=True)
    df['收盘价'] = df['收盘价'].ffill()
    df['PE_TTM'] = df['PE_TTM'].ffill()
    if has_sw:
        df['行业指数收盘价'] = df['行业指数收盘价'].ffill()

    drop_cols = ['收盘价', 'PE_TTM']
    if has_sw:
        drop_cols.append('行业指数收盘价')
    df = df.dropna(subset=drop_cols)

    # 归一化
    print("5. 归一化...")
    first_close = df['收盘价'].iloc[0]
    first_pe = df['PE_TTM'].iloc[0]
    df['close_norm'] = df['收盘价'] / first_close
    df['pe_norm'] = df['PE_TTM'] / first_pe

    if has_sw:
        first_sw = df['行业指数收盘价'].iloc[0]
        df['sw_norm'] = df['行业指数收盘价'] / first_sw

    base_date = df['日期'].iloc[0].strftime('%Y-%m-%d')

    # 计算Y轴范围 (实际最大值+10%, 最小值-5%)
    all_vals = df['close_norm'].tolist() + df['pe_norm'].tolist()
    if has_sw:
        all_vals += df['sw_norm'].tolist()
    data_max = max(all_vals)
    data_min = min(all_vals)
    data_range = data_max - data_min
    y_max = data_max + data_range * 0.10
    y_min = data_min - data_range * 0.05
    # 确保 y_min 不低于 0
    y_min = max(y_min, 0)

    dates = df['日期'].dt.strftime('%Y-%m-%d').tolist()
    close_norm = [round(v, 4) for v in df['close_norm'].tolist()]
    pe_norm = [round(v, 4) for v in df['pe_norm'].tolist()]
    if has_sw:
        sw_norm = [round(v, 4) for v in df['sw_norm'].tolist()]

    end_close = close_norm[-1]
    end_pe = pe_norm[-1]
    if has_sw:
        end_sw = sw_norm[-1]

    last_close = df['收盘价'].iloc[-1]
    last_pe = df['PE_TTM'].iloc[-1]
    if has_sw:
        last_sw = df['行业指数收盘价'].iloc[-1]

    print(f"   基准日: {base_date}")
    print(f"   收盘价: {first_close:.2f} -> {last_close:.2f} ({(end_close-1)*100:+.1f}%)")
    print(f"   PE TTM: {first_pe:.2f} -> {last_pe:.2f} ({(end_pe-1)*100:+.1f}%)")
    if has_sw:
        print(f"   行业指数: {first_sw:.2f} -> {last_sw:.2f} ({(end_sw-1)*100:+.1f}%)")
    print(f"   Y轴范围: [{y_min:.2f}, {y_max:.2f}]")

    # 构建 trace 和汇总表
    traces_js = f"""var trace1 = {{
  x: dates,
  y: {json.dumps(close_norm)},
  mode: 'lines+markers',
  name: '{name}收盘价',
  line: {{ color: '#E63946', width: 2 }},
  marker: {{ size: 4, color: '#E63946' }}
}};
var trace2 = {{
  x: dates,
  y: {json.dumps(pe_norm)},
  mode: 'lines+markers',
  name: 'PE(TTM)',
  line: {{ color: '#FF8C00', width: 2 }},
  marker: {{ size: 4, color: '#FF8C00', symbol: 'diamond' }}
}};"""

    traces_list = "trace1, trace2"

    legend_sw = ""
    summary_sw_row = ""

    if has_sw:
        traces_js += f"""
var trace3 = {{
  x: dates,
  y: {json.dumps(sw_norm)},
  mode: 'lines+markers',
  name: '{sw_name}',
  line: {{ color: '#2A9D8F', width: 2 }},
  marker: {{ size: 4, color: '#2A9D8F' }}
}};"""
        traces_list = "trace1, trace2, trace3"

        legend_sw = f'<div class="legend-item"><div class="legend-dot" style="background:#2A9D8F"></div> {sw_name}</div>'

        sw_class = 'neg' if end_sw < 1 else 'pos'
        summary_sw_row = f"""<tr><td>{sw_name}</td><td>{first_sw:.2f}</td><td>{last_sw:.2f}</td><td>{end_sw:.4f}</td><td class=\"{sw_class}\">{(end_sw-1)*100:+.1f}%</td></tr>"""

    close_class = 'neg' if end_close < 1 else 'pos'
    pe_class = 'neg' if end_pe < 1 else 'pos'

    data_source_note = "AKShare" + (f"（新浪/百度/申万）" if has_sw else "（新浪/百度）")

    # 生成HTML
    print("6. 生成HTML...")
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name}({code}) 归一化走势</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif; background: #f8f9fa; padding: 20px; }}
  .container {{ max-width: 1100px; margin: 0 auto; }}
  h1 {{ color: #2B579A; font-size: 20px; margin-bottom: 5px; }}
  .subtitle {{ color: #808080; font-size: 13px; margin-bottom: 20px; }}
  #chart {{ width: 100%; height: 520px; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
  .legend-box {{ display: flex; gap: 30px; justify-content: center; margin-top: 15px; flex-wrap: wrap; }}
  .legend-item {{ display: flex; align-items: center; gap: 8px; font-size: 14px; }}
  .legend-dot {{ width: 14px; height: 14px; border-radius: 50%; }}
  .summary {{ margin-top: 20px; background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
  .summary h2 {{ font-size: 15px; color: #2B579A; margin-bottom: 12px; }}
  .summary table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .summary th {{ background: #2B579A; color: #fff; padding: 10px 12px; text-align: center; }}
  .summary td {{ padding: 8px 12px; text-align: center; border-bottom: 1px solid #eee; }}
  .summary tr:nth-child(even) td {{ background: #f5f7fa; }}
  .pos {{ color: #e63946; font-weight: bold; }}
  .neg {{ color: #2a9d8f; font-weight: bold; }}
</style>
</head>
<body>
<div class="container">
  <h1>{name}({code}) 归一化走势（首日 = 1.0）</h1>
  <div class="subtitle">基准日：{base_date} ｜ 数据源：{data_source_note} ｜ 区间：{dates[0]} ~ {dates[-1]}</div>
  <div id="chart"></div>
  <div class="legend-box">
    <div class="legend-item"><div class="legend-dot" style="background:#E63946"></div> {name}收盘价</div>
    <div class="legend-item"><div class="legend-dot" style="background:#FF8C00"></div> PE(TTM)</div>
    {legend_sw}
  </div>
  <div class="summary">
    <h2>区间涨跌汇总</h2>
    <table>
      <tr><th>指标</th><th>基准日值</th><th>末日值</th><th>归一化</th><th>变化幅度</th></tr>
      <tr><td>{name}收盘价</td><td>{first_close:.2f}</td><td>{last_close:.2f}</td><td>{end_close:.4f}</td><td class="{close_class}">{(end_close-1)*100:+.1f}%</td></tr>
      <tr><td>PE(TTM)</td><td>{first_pe:.2f}</td><td>{last_pe:.2f}</td><td>{end_pe:.4f}</td><td class="{pe_class}">{(end_pe-1)*100:+.1f}%</td></tr>
      {summary_sw_row}
    </table>
  </div>
</div>
<script>
var dates = {json.dumps(dates)};
{traces_js}
var layout = {{
  margin: {{ t: 30, b: 60, l: 60, r: 40 }},
  xaxis: {{
    title: '日期',
    tickangle: -45,
    nticks: 15,
    gridcolor: '#eee',
    zeroline: false
  }},
  yaxis: {{
    title: '归一化值（首日=1.0）',
    range: [{y_min:.2f}, {y_max:.2f}],
    gridcolor: '#eee',
    zeroline: true,
    zerolinecolor: '#ccc',
    tickformat: '.2f'
  }},
  hovermode: 'x unified',
  legend: {{ orientation: 'h', y: -0.25 }},
  plot_bgcolor: '#fff',
  paper_bgcolor: '#fff',
  showlegend: true
}};
Plotly.newPlot('chart', [{traces_list}], layout, {{ responsive: true }});
</script>
</body>
</html>'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"7. 完成: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description='A股个股归一化走势图生成器')
    parser.add_argument('stock', help='股票代码或名称（如 600519 或 贵州茅台）')
    parser.add_argument('--days', type=int, default=365, help='回溯天数（默认365天）')
    parser.add_argument('--output', type=str, default=None, help='输出文件路径（默认当前目录）')
    args = parser.parse_args()

    # 解析股票代码
    print(f"=== 解析股票: {args.stock} ===")
    code, sina_prefix, em_prefix = resolve_stock_code(args.stock)
    name = get_stock_name(code, em_prefix)
    print(f"  股票: {name}({code}), 前缀: {sina_prefix}/{em_prefix}")

    # 计算日期范围
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y%m%d')
    print(f"  日期范围: {start_date} ~ {end_date} ({args.days}天)")

    # 获取数据
    print(f"\n=== 获取数据 ===")
    df_price, df_pe, df_sw, sw_name = fetch_data(code, em_prefix, sina_prefix, start_date, end_date)

    # 输出路径
    if args.output:
        output_path = args.output
    else:
        # 使用ASCII文件名避免预览问题
        safe_name = re.sub(r'[^\w]', '', name) if name else code
        output_path = f'{safe_name}_normalized_chart.html'

    # 生成图表
    print(f"\n=== 生成图表 ===")
    generate_chart(code, name, df_price, df_pe, df_sw, sw_name, output_path)


if __name__ == '__main__':
    main()
