import tushare as ts
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import requests
import json
import re

load_dotenv()

class StockService:
    def __init__(self):
        self.token = os.getenv('TUSHARE_TOKEN')
        # 禁用Tushare API，直接使用国内股价API
        self.use_tushare = False
        self.pro = None
        print("使用国内股价API: 东方财富、腾讯、新浪")
        
    def format_stock_code(self, stock_code):
        """格式化股票代码，添加市场后缀"""
        if '.' not in stock_code:
            # 自动判断股票市场
            if stock_code.startswith('6'):
                return f"{stock_code}.SH"
            elif stock_code.startswith('0') or stock_code.startswith('3'):
                return f"{stock_code}.SZ"
            elif stock_code.startswith('4') or stock_code.startswith('8'):
                return f"{stock_code}.BJ"  # 北交所
            elif stock_code.startswith('5') or stock_code.startswith('1'):
                return f"{stock_code}.SH"  # 上证基金
            elif stock_code.startswith('9'):
                return f"{stock_code}.SH"  # B股
            else:
                return f"{stock_code}.SZ"  # 默认深市
        return stock_code
        
    def get_stock_info(self, stock_code):
        """获取股票基本信息"""
        stock_code = self.format_stock_code(stock_code)
        result = None
        
        # 尝试使用Tushare
        if self.use_tushare:
            try:
                df = self.pro.daily_basic(ts_code=stock_code, 
                                        fields='ts_code,symbol,name,area,industry,list_date')
                if not df.empty:
                    result = df.iloc[0].to_dict()
            except Exception as e:
                print(f"Tushare获取股票信息失败: {e}")
        
        # 尝试使用东方财富接口
        if result is None:
            try:
                simple_code = stock_code.split('.')[0]
                url = f"https://searchapi.eastmoney.com/api/suggest/get?input={simple_code}&type=14&token=D43BF722C8E33BDC906FB84D85E326E8"
                response = requests.get(url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('QuotationCodeTable', {}).get('Data'):
                        for item in data['QuotationCodeTable']['Data']:
                            if item.get('Code') == simple_code:
                                # 尝试获取实时价格
                                current_price, price_precision = self.get_realtime_price(stock_code)
                                return {
                                    'ts_code': stock_code,
                                    'symbol': simple_code,
                                    'name': item.get('Name', ''),
                                    'area': '',
                                    'industry': item.get('QuotationCodeTableMarket', {}).get('Name', ''),
                                    'list_date': '',
                                    'current_price': current_price or 0,
                                    'price_precision': price_precision
                                }
            except Exception as e:
                print(f"东方财富接口失败: {e}")
        
        # 尝试使用新浪API
        if result is None:
            try:
                code_prefix = 'sh' if stock_code.endswith('.SH') else 'sz'
                simple_code = stock_code.split('.')[0]
                query_code = f"{code_prefix}{simple_code}"
                    
                url = f"http://hq.sinajs.cn/list={query_code}"
                headers = {"Referer": "https://finance.sina.com.cn"}
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    content = response.text
                    # 解析返回数据
                    matches = re.findall(r'hq_str_(?:\w+)=\"([^\"]+)\"', content)
                    if matches and len(matches[0].split(',')) > 1:
                        data = matches[0].split(',')
                        price_str = data[3] if len(data) > 3 else "0"
                        price = float(price_str) if price_str else 0
                        # 确定价格精度
                        price_precision = len(price_str.split('.')[1]) if '.' in price_str else 0
                        
                        return {
                            'ts_code': stock_code,
                            'symbol': simple_code,
                            'name': data[0],
                            'area': '',
                            'industry': '',
                            'list_date': '',
                            'current_price': price,
                            'price_precision': price_precision
                        }
            except Exception as e:
                print(f"新浪API获取股票信息失败: {e}")
        
        # 尝试使用腾讯API
        if result is None:
            try:
                simple_code = stock_code.split('.')[0]
                market = 'sh' if stock_code.endswith('.SH') else 'sz'
                query_code = f"{market}{simple_code}"
                
                url = f"https://qt.gtimg.cn/q={query_code}"
                response = requests.get(url)
                
                if response.status_code == 200:
                    content = response.text
                    # 解析返回数据
                    pattern = r'v_.*="(.*)"'
                    matches = re.findall(pattern, content)
                    if matches and len(matches[0].split('~')) > 1:
                        data = matches[0].split('~')
                        price_str = data[3] if len(data) > 3 else "0"
                        price = float(price_str) if price_str else 0
                        # 确定价格精度
                        price_precision = len(price_str.split('.')[1]) if '.' in price_str else 0
                        
                        return {
                            'ts_code': stock_code,
                            'symbol': simple_code,
                            'name': data[1],
                            'area': '',
                            'industry': '',
                            'list_date': '',
                            'current_price': price,
                            'price_precision': price_precision
                        }
            except Exception as e:
                print(f"腾讯API获取股票信息失败: {e}")
                
        return result
            
    def get_realtime_price(self, stock_code):
        """获取实时股价，返回价格和价格精度"""
        if not stock_code:
            print("警告: 传入的股票代码为空")
            return None, 2
            
        try:
            stock_code = self.format_stock_code(stock_code)
        except Exception as e:
            print(f"格式化股票代码出错: {e}")
        
        price = None
        price_precision = 2  # 默认精度为2位小数
        
        # 尝试使用腾讯股票API（更适合实时行情）
        try:
            market = 'sh' if stock_code.endswith('.SH') else 'sz'
            simple_code = stock_code.split('.')[0]
            query_code = f"{market}{simple_code}"
            
            url = f"https://qt.gtimg.cn/q={query_code}"
            response = requests.get(url, timeout=5)  # 添加超时
            
            if response.status_code == 200:
                content = response.text
                pattern = r'v_.*="(.*)"'
                matches = re.findall(pattern, content)
                if matches and len(matches[0].split('~')) > 3:
                    data = matches[0].split('~')
                    try:
                        price_str = data[3]
                        price = float(price_str)
                        
                        # 确定价格精度
                        if '.' in price_str:
                            price_precision = len(price_str.split('.')[1])
                        else:
                            price_precision = 0
                            
                        if price > 0:
                            return price, price_precision
                    except (ValueError, IndexError) as e:
                        print(f"腾讯API返回的价格解析失败: {e}")
        except Exception as e:
            print(f"腾讯API获取实时价格失败: {e}")
                
        # 如果腾讯API失败，尝试使用新浪财经API
        if price is None:
            try:
                code_prefix = 'sh' if stock_code.endswith('.SH') else 'sz'
                simple_code = stock_code.split('.')[0]
                query_code = f"{code_prefix}{simple_code}"
                    
                url = f"http://hq.sinajs.cn/list={query_code}"
                headers = {"Referer": "https://finance.sina.com.cn"}
                response = requests.get(url, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    content = response.text
                    # 解析返回数据
                    matches = re.findall(r'hq_str_(?:\w+)=\"([^\"]+)\"', content)
                    if matches and len(matches[0].split(',')) > 3:
                        data = matches[0].split(',')
                        try:
                            price_str = data[3]
                            price = float(price_str)
                            
                            # 确定价格精度
                            if '.' in price_str:
                                price_precision = len(price_str.split('.')[1])
                            else:
                                price_precision = 0
                                
                            if price > 0:
                                return price, price_precision
                        except (ValueError, IndexError) as e:
                            print(f"新浪API返回的价格解析失败: {e}")
            except Exception as e:
                print(f"新浪API获取实时价格失败: {e}")
            
        # 尝试东方财富数据接口
        if price is None:
            try:
                simple_code = stock_code.split('.')[0]
                market = 0 if stock_code.endswith('.SZ') else 1  # 深市=0，沪市=1
                url = f"https://push2.eastmoney.com/api/qt/stock/get?ut=fa5fd1943c7b386f172d6893dbfba10b&invt=2&fltt=2&fields=f43,f57,f58,f169,f170,f46,f44,f51,f168,f47,f164,f163,f116,f60,f45,f52,f50,f48,f167,f117,f71,f161,f49,f530,f135,f136,f137,f138,f139,f141,f142,f144,f145,f147,f148,f140,f143,f146,f149,f55,f62,f162,f92,f173,f104,f105,f84,f85,f183,f184,f185,f186,f187,f188,f189,f190,f191,f192,f107,f111,f86,f177,f78,f110,f262,f263,f264,f267,f268,f250,f251,f252,f253,f254,f255,f256,f257,f258,f266,f269,f270,f271,f273,f274,f275,f127,f199,f128,f193,f196,f194,f195,f197,f80,f280,f281,f282,f284,f285,f286,f287,f292&secid={market}.{simple_code}&cb=jQuery183020305881136688065_1638156597200&_=1638156597200"
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    content = response.text
                    # 从jQuery回调中提取JSON数据
                    json_data = re.findall(r'jQuery[0-9_]+\((.*)\)', content)
                    if json_data:
                        try:
                            data = json.loads(json_data[0])
                            if 'data' in data and 'f43' in data['data']:
                                # f43是最新价
                                price_val = data['data']['f43'] / 100  # 价格可能需要除以100
                                price_str = str(price_val)
                                
                                # 确定价格精度
                                price_precision = len(price_str.split('.')[1]) if '.' in price_str else 0
                                return price_val, price_precision
                        except (ValueError, KeyError, IndexError) as e:
                            print(f"东方财富数据解析失败: {e}")
            except Exception as e:
                print(f"东方财富API获取实时价格失败: {e}")
                
        return None, price_precision
        
    def check_price_targets(self, trade):
        """检查股票价格是否达到目标"""
        current_price, _ = self.get_realtime_price(trade.stock_code)
        if current_price:
            if current_price >= trade.sell_target:
                return "卖出"
            if current_price <= trade.buy_target:
                return "买入"
        return None

    def get_historical_data(self, stock_code, days=30):
        """获取历史数据"""
        stock_code = self.format_stock_code(stock_code)
        
        # 尝试使用Tushare
        if self.use_tushare:
            try:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                
                df = self.pro.daily(ts_code=stock_code, 
                                  start_date=start_date.strftime('%Y%m%d'), 
                                  end_date=end_date.strftime('%Y%m%d'))
                
                if not df.empty:
                    # 按日期排序
                    df = df.sort_values('trade_date')
                    return df[['trade_date', 'open', 'high', 'low', 'close', 'vol']]
            except Exception as e:
                print(f"Tushare获取历史数据失败: {e}")
        
        # 尝试东方财富接口
        try:
            simple_code = stock_code.split('.')[0]
            market = 0 if stock_code.endswith('.SZ') else 1
            url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&secid={market}.{simple_code}&beg=0&end=20500000&lmt={days}"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if data['data'] and data['data']['klines']:
                    klines = data['data']['klines']
                    result = []
                    for line in klines:
                        parts = line.split(',')
                        result.append({
                            'trade_date': parts[0],
                            'open': float(parts[1]),
                            'close': float(parts[2]),
                            'high': float(parts[3]),
                            'low': float(parts[4]),
                            'vol': float(parts[5])
                        })
                    return pd.DataFrame(result)
        except Exception as e:
            print(f"东方财富获取历史数据失败: {e}")
        
        # 新浪API: 日线数据
        try:
            market = 'sh' if stock_code.endswith('.SH') else 'sz'
            simple_code = stock_code.split('.')[0]
            
            url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={market}{simple_code}&scale=240&ma=no&datalen={days}"
            response = requests.get(url)
            
            if response.status_code == 200 and response.text:
                data = json.loads(response.text)
                df = pd.DataFrame(data)
                if not df.empty:
                    df.rename(columns={
                        'day': 'trade_date',
                        'open': 'open',
                        'high': 'high',
                        'low': 'low',
                        'close': 'close',
                        'volume': 'vol'
                    }, inplace=True)
                    # 确保数值类型
                    for col in ['open', 'high', 'low', 'close']:
                        df[col] = pd.to_numeric(df[col])
                    df['vol'] = pd.to_numeric(df['vol'])
                    return df
        except Exception as e:
            print(f"新浪API获取历史数据失败: {e}")
        
        # 腾讯API: 获取历史日K
        try:
            market = 'sh' if stock_code.endswith('.SH') else 'sz'
            simple_code = stock_code.split('.')[0]
            
            today = datetime.now().strftime('%Y-%m-%d')
            start_day = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{simple_code},day,{start_day},{today},60,qfq"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if data['code'] == 0 and data['data']:
                    kline_key = 'qfqday' if 'qfqday' in data['data'][f"{market}{simple_code}"] else 'day'
                    klines = data['data'][f"{market}{simple_code}"][kline_key]
                    result = []
                    for k in klines:
                        result.append({
                            'trade_date': k[0],
                            'open': float(k[1]),
                            'close': float(k[2]),
                            'high': float(k[3]),
                            'low': float(k[4]),
                            'vol': float(k[5])
                        })
                    return pd.DataFrame(result)
        except Exception as e:
            print(f"腾讯API获取历史数据失败: {e}")
            
        return None
        
    def search_stocks(self, keyword):
        """搜索股票"""
        results = []
        
        # 使用东方财富搜索接口
        try:
            url = f"https://searchapi.eastmoney.com/api/suggest/get?input={keyword}&type=14&token=D43BF722C8E33BDC906FB84D85E326E8"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('QuotationCodeTable', {}).get('Data'):
                    for item in data['QuotationCodeTable']['Data']:
                        code = item.get('Code', '')
                        if not code:
                            continue
                            
                        # 处理深市和沪市代码
                        if code.startswith('6'):
                            ts_code = f"{code}.SH"
                        elif code.startswith('0') or code.startswith('3'):
                            ts_code = f"{code}.SZ"
                        else:
                            # 跳过非常规股票代码
                            continue
                            
                        # 创建股票数据记录
                        stock_data = {
                            'ts_code': ts_code,
                            'symbol': code,
                            'name': item.get('Name', ''),
                            'area': '',
                            'industry': item.get('QuotationCodeTableMarket', {}).get('Name', ''),
                            'list_date': ''
                        }
                        
                        # 尝试获取当前价格
                        try:
                            current_price, price_precision = self.get_realtime_price(ts_code)
                            if current_price:
                                stock_data['current_price'] = current_price
                                stock_data['price_precision'] = price_precision
                        except Exception as e:
                            print(f"获取{ts_code}价格错误: {e}")
                            
                        results.append(stock_data)
        except Exception as e:
            print(f"搜索股票失败: {e}")
            
        # 如果东方财富没有结果，尝试使用新浪API
        if not results:
            try:
                # 对于数字，假设是股票代码
                if keyword.isdigit():
                    # 尝试沪市和深市
                    for market in ['sh', 'sz']:
                        url = f"http://hq.sinajs.cn/list={market}{keyword}"
                        headers = {"Referer": "https://finance.sina.com.cn"}
                        response = requests.get(url, headers=headers)
                        
                        if response.status_code == 200:
                            content = response.text
                            matches = re.findall(r'hq_str_(?:\w+)=\"([^\"]+)\"', content)
                            if matches and len(matches[0].split(',')) > 1:
                                data = matches[0].split(',')
                                name = data[0]
                                if name:  # 如果名称不为空，说明找到了股票
                                    ts_code = f"{keyword}.{'SH' if market == 'sh' else 'SZ'}"
                                    current_price, price_precision = self.get_realtime_price(ts_code)
                                    
                                    record = {
                                        'ts_code': ts_code,
                                        'symbol': keyword,
                                        'name': name,
                                        'area': '',
                                        'industry': '',
                                        'list_date': ''
                                    }
                                    if current_price:
                                        record['current_price'] = current_price
                                        record['price_precision'] = price_precision
                                    
                                    results.append(record)
                # 对于非数字，假设是股票名称
                else:
                    # 这里需要更复杂的逻辑来通过名称查找，暂不实现
                    pass
            except Exception as e:
                print(f"通过新浪API搜索股票失败: {e}")
                    
        return results 