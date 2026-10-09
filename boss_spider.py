from DrissionPage import ChromiumPage,ChromiumOptions
from get_user_agent import get_user_agent_of_pc
import time
import random
import requests
import threading
# page.listen.start('joblist.json')
from typing import Optional, Dict
import os
import csv
from urllib.parse import quote, unquote
# 城市名称 -> BOSS直聘城市ID 映射
CITY_MAP = {
    '北京': '101010100', '上海': '101020100', '天津': '101030100', '重庆': '101040100',
    '哈尔滨': '101050100', '长春': '101060100', '沈阳': '101070100', '大连': '101070200',
    '石家庄': '101090100', '太原': '101100100', '西安': '101110100', '济南': '101120100',
    '青岛': '101120200', '郑州': '101180100', '南京': '101190100', '苏州': '101190400',
    '无锡': '101190200', '常州': '101191100', '武汉': '101200100', '杭州': '101210100',
    '宁波': '101210400', '温州': '101210300', '合肥': '101220100', '福州': '101230100',
    '厦门': '101230200', '南昌': '101240100', '长沙': '101250100', '贵阳': '101260100',
    '成都': '101270100', '昆明': '101290100', '广州': '101280100', '深圳': '101280600',
    '佛山': '101280800', '东莞': '101281600', '珠海': '101280700', '中山': '101281700',
    '惠州': '101280300', '南宁': '101300100', '海口': '101310100', '嘉兴': '101210500',
    '绍兴': '101210600', '台州': '101210700', '金华': '101210900', '洛阳': '101180900',
    '徐州': '101190800', '扬州': '101190600', '南通': '101190500', '烟台': '101120500',
    '潍坊': '101120600', '临沂': '101120900', '潍坊': '101120600', '保定': '101090200',
    '唐山': '101090500', '廊坊': '101090600', '泉州': '101230500', '漳州': '101230600',
    '株洲': '101250300', '湘潭': '101250200', '咸阳': '101110200', '芜湖': '101220300',
}

def load_config():
    """从 config.txt 读取关键词和城市（支持直接填城市名称）"""
    cfg_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.txt')
    defaults = {'keyword': '数据采集', 'city': '杭州'}
    if not os.path.exists(cfg_file):
        with open(cfg_file, 'w', encoding='utf-8') as f:
            f.write('# BOSS直聘爬虫配置\n')
            f.write('# keyword= 改成你要搜索的岗位关键词\n')
            f.write('# city= 直接填城市名称，如：广州、深圳、杭州（也可填城市ID）\n')
            f.write(f"keyword={defaults['keyword']}\n")
            f.write(f"city={defaults['city']}\n")
        print(f"[配置] 已创建配置文件: {cfg_file}")
    cfg = {}
    with open(cfg_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                cfg[k.strip()] = v.strip()
    keyword = cfg.get('keyword', defaults['keyword'])
    city_raw = cfg.get('city', defaults['city']).strip()
    # 城市：纯数字直接用ID，否则按名称查表
    if city_raw.isdigit():
        city = city_raw
    else:
        city = CITY_MAP.get(city_raw, '')
        if not city:
            print(f"[警告] 未找到城市「{city_raw}」的ID，已回退到杭州")
            city = '101210100'
    print(f"[配置] 关键词: {keyword} | 城市: {city_raw} (ID:{city})")
    return {
        "start_url": f'https://www.zhipin.com/web/geek/jobs?city={city}&query={keyword}',
        "heart_time": 15,
        "keyword": quote(keyword),
        "keyword_raw": keyword,
        "city": city
    }

Config = load_config()
class BossDP:
    def __init__(self):
        self.urgent_event=threading.Event()#设置紧急心跳信号
        co=ChromiumOptions()
        import os as _os
        for _p in [r'C:\Program Files\Google\Chrome\Application\chrome.exe', r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe']:
            if _os.path.exists(_p): co.set_browser_path(_p); break
        co.set_local_port(9333)
        co.set_user_data_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'browser_profile'))
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--no-sandbox')#初始化了浏览器模拟浏览器指纹
        co.set_user_agent(get_user_agent_of_pc())
        co.set_argument('--window-size','1920,1080')
        self.page=ChromiumPage(co)
        self.page.run_cdp('Page.addScriptToEvaluateOnNewDocument', source='''
                // 1. 伪造内存大小 (解决 CHR_MEMORY FAIL)
                Object.defineProperty(navigator, 'deviceMemory', {
                    value: 8, 
                    writable: false, 
                    configurable: true, 
                    enumerable: false
                });

                // 2. CPU 核心数
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    value: 8, 
                    writable: false, 
                    configurable: true, 
                    enumerable: false
                });
            '''
        )
        #初始化requests
        self.session=requests.Session()
        self.current_cookies={}
        self.current_headers={}
        #存储数据
        self.all_jobs=[]
        self.seen_job_ids=set()
        self.company_cache={}
        self.stats={
            'page':0,
            "jobs_fetched":0,
            "details_success":0
        }
    def login(self):
        #登陆账号，准备获取cookies
        self.page.get(Config['start_url'])
        print("准备登陆")
        input("登陆完成后回车继续任务")
        #同步初始cookies和headers
        self.get_cookie_headers()
        
    def get_cookie_headers(self):
        try:
            cookies_list = self.page.cookies()
            # 将列表转换为字典
            cookies_dict = {}
            for cookie in cookies_list:
                if 'name' in cookie and 'value' in cookie:
                    cookies_dict[cookie['name']] = cookie['value']
            self.session.cookies.clear()
            for k, v in cookies_dict.items():
                self.session.cookies.set(k, v)
            self.current_cookies = cookies_dict
            self.session.cookies.update(cookies_dict)
            self.current_headers={
                "User-Agent":get_user_agent_of_pc(),
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/x-www-form-urlencoded',
                'origin': 'https://www.zhipin.com',
                'referer': f'https://www.zhipin.com/web/geek/jobs?city={Config["city"]}&query={Config["keyword"]}',
                'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,en-GB;q=0.6',
                'priority': 'u=1, i',
            }
            self.session.headers.update(self.current_headers)
            return True
        except Exception as e:
            print("同步cookies失败",e)
            return False
    def click_job(self):
        try:
            job_list=self.page.ele('.rec-job-list',timeout=5)
            jobs=job_list.eles('.job-card-box') if job_list else []
            print(f"提取到{len(jobs)}个岗位卡片")
            if not jobs:
                return
            job=random.choice(jobs)
            try:
                job_name=job.ele(".job-name",timeout=2)
                print(f"拟人点击岗位:{job_name.text}")
                job.click()
                time.sleep(2)
                self.get_cookie_headers()
            except Exception as e:
                print("点击岗位失败",e)
        except Exception as e:
            print("查找岗位集失败",e)
      # ================= 心跳线程（定期模拟操作保活） =================
    def start_heartbeat(self):
        """后台线程：定期点击岗位 + 滚动，维持 cookies 有效"""
        def heartbeat_task():
            print(f"[心跳线程] 启动，每 {Config['heart_time']} 秒执行一次拟人操作\n")
            time.sleep(5)  # 等待页面稳定
            
            while True:
                is_urgent=self.urgent_event.wait(timeout=Config['heart_time'])#设置紧急心跳
                if is_urgent:
                    print(f"【心跳】收到紧急信号，立刻执行")
                    self.urgent_event.clear()
                try:
                    #检查是否跳转首页
                    current_url = self.page.url
                    is_homepage = current_url == "https://www.zhipin.com/"
                    if is_homepage:
                        print(f" [心跳] 检测到跳转到首页，重新加载列表页...")
                        self.page.get(Config['start_url'])  # 直接重新加载你的目标列表页
                        time.sleep(3)
                        self.get_cookie_headers()
                        continue
                    # 随机决定是否滚动
                    if random.random() > 0.2:
                        for i in range(3):
                            distance = random.randint(10,15)
                            self.page.scroll.down(distance)
                        time.sleep(1)

                    # 点击随机岗位（核心保活动作）
                    self.click_job()
                    
                except Exception as e:
                    print(f" 心跳线程异常: {e}")
        thread = threading.Thread(target=heartbeat_task, daemon=True)
        thread.start()

    #通过api获取信息
    def api_job_list(self,page:int =1,keyword:str=Config['keyword'])->Optional[Dict]:
        self.get_cookie_headers()#请求前同步cookies
        url="https://www.zhipin.com/wapi/zpgeek/search/joblist.json"
        data_str = (
        f"page={page}&"
        f"pageSize=30&"
        f"city={Config['city']}&"
        f"query={keyword}&"
        f"scene=1"
        )
        try:
            res=self.session.post(url,data=data_str,headers=self.current_headers,timeout=15)
            if res.status_code==200:
                result=res.json()
                if result.get('code')==0:
                    return result
                else:
                    print("列表接口错误")
                    return None
            else:
                print(f"HTTP:{res.status_code}")
                return None
        except Exception as e:
            print("请求列表失败",e)
            return None
    def api_job_detail(self,security_id:str):#通过api获得详情信息
        self.get_cookie_headers()
        url="https://www.zhipin.com/wapi/zpgeek/job/detail.json"
        params={"securityId":security_id}
        try:
            res=self.session.get(url,params=params,timeout=15)
            if res.status_code==200:
                result=res.json()
                if result.get('code')==0:
                    return result
                else:
                    return None
            return None
        except Exception as e:
            print("请求详情失败",e)
            return None
#详情只需要需要工作介绍，详细地址，公司介绍
    def parse_job_detail(self,result):
        zp_data=result['zpData']
        job_info=zp_data['jobInfo']
        brand_info=zp_data['brandComInfo']
        out = {
            "工作介绍":job_info['postDescription'],
            "工作详细地址":job_info['address'],
            "公司介绍":brand_info.get('introduce','')
        }
        if job_info.get('latitude'): out['纬度'] = job_info['latitude']
        if job_info.get('longitude'): out['经度'] = job_info['longitude']
        if job_info.get('locationName'): out['位置标签'] = job_info['locationName']
        if brand_info.get('brandName'):
            out['公司全称'] = brand_info['brandName']
        return out

    def extract_contact(self, text: str) -> str:
        """从文本中提取联系方式：邮箱/手机/座机/微信/QQ"""
        import re
        if not text:
            return ''
        found=[]
        for x in re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', text):
            found.append('邮箱:'+x)
        for x in re.findall(r'1[3-9]\d{9}', text):
            found.append('电话:'+x)
        for x in re.findall(r'(?<!\d)(0\d{2,3}-?\d{7,8})(?!\d)', text):
            found.append('座机:'+x)
        for x in re.findall(r'(?:微信|wx|vx|weixin)[：: ]*([A-Za-z0-9_\-]{5,20})', text, re.I):
            found.append('微信:'+x)
        for x in re.findall(r'QQ[：: ]*(\d{5,12})', text, re.I):
            found.append('QQ:'+x)
        seen=set(); out=[]
        for x in found:
            if x not in seen:
                seen.add(x); out.append(x)
        return '；'.join(out)

    def fetch_company_info(self, brand_id: str) -> dict:
        """打开公司主页抓取公司简介/地址/联系方式（同一家公司只抓一次）"""
        import re
        if not brand_id:
            return {}
        if brand_id in self.company_cache:
            return self.company_cache[brand_id]
        info = {'公司主页':'', '公司全称':'', '公司简介':'', '主营产品':'', '公司地址':'', '联系方式':'',
                '统一社会信用代码':'', '法定代表人':'', '注册资本':'', '成立日期':'', '注册地址':'', '经营范围':'', '经营状态':''}
        try:
            url = f"https://www.zhipin.com/gongsi/{brand_id}.html"
            info['公司主页'] = url
            self.page.get(url)
            time.sleep(random.uniform(2,4))
            try:
                t = self.page.title or ''
                info['公司全称'] = t.replace(' - BOSS直聘','').replace('- BOSS直聘','').strip()
            except:
                pass
            full = ''
            try:
                full = self.page.ele('body', timeout=1).text or ''
            except:
                pass
            # 清洗噪音行
            lines = []
            for ln in full.split('\n'):
                s = ln.strip()
                if not s:
                    continue
                if s in ('收藏','分享','举报','在招职位','公司环境','招聘动态','公司地址','工商信息'):
                    continue
                lines.append(s)
            clean = '\n'.join(lines)
            info['公司简介'] = clean[:1500]
            # 主营产品：找关键词段落
            import re as _re
            m = _re.search(r'(主营[^\n]{0,80}|主营业务[^\n]{0,80}|主打[^\n]{0,80}|主要产品[^\n]{0,80})', clean)
            if m:
                info['主营产品'] = m.group(0).strip()[:200]
            if not info['主营产品']:
                info['主营产品'] = clean[:200].strip()
            # 工商信息字段解析
            def _pick(pattern, text, group=1):
                mm = _re.search(pattern, text)
                return mm.group(group).strip() if mm else ''
            info['统一社会信用代码'] = _pick(r'统一社会信用代码[:：]?\s*([0-9A-Z]{15,18})', clean)
            info['法定代表人'] = _pick(r'法定代表人[:：]?\s*([^\n\r]{1,20})', clean)
            info['注册资本'] = _pick(r'注册资本[:：]?\s*([^\n\r]{1,30})', clean)
            info['成立日期'] = _pick(r'成立(?:日期|时间)?[:：]?\s*(\d{4}[-年/]\d{1,2}[-月/]\d{1,2}日?)', clean)
            info['注册地址'] = _pick(r'注册地址[:：]?\s*([^\n\r]{5,150})', clean)
            info['经营状态'] = _pick(r'经营状态[:：]?\s*([^\n\r]{1,20})', clean)
            info['经营范围'] = _pick(r'经营范围[:：]?\s*([^\n\r]{20,800})', clean)
            # 公司地址：优先注册地址，其次常见地址行
            if not info['注册地址']:
                m2 = _re.search(r'((?:广东|广州|深圳|上海|北京|浙江|杭州|东莞|佛山|中山|珠海|惠州|江门|汕头|湛江|肇庆|韶关|清远|梅州|河源|阳江|茂名|潮州|揭阳|云浮|汕尾)[^\n]{0,80})', clean)
                if m2:
                    info['公司地址'] = m2.group(0).strip()[:120]
            else:
                info['公司地址'] = info['注册地址'][:150]
            # 联系方式
            info['联系方式'] = self.extract_contact(full[:4000])
            print(f"   公司: {info['公司全称'][:18]} | 信用代码: {info['统一社会信用代码'][:6] or '无'} | 注册地址: {info['注册地址'][:24] or '无'}")
        except Exception as e:
            print(f" 公司页抓取失败: {e}")
        self.company_cache[brand_id] = info
        return info
    def is_relevant(self,job_name):
        # 按 config.txt 里的关键词匹配（改关键词即改采集范围）
        kw = Config.get('keyword_raw','')
        if kw:
            return kw.lower() in (job_name or '').lower()
        return True

    def crawl(self,max_pages,keyword:str=Config['keyword'],target:int=0):
        hist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "导出结果", "boss_jobs.csv")
        if os.path.exists(hist_path):
            try:
                with open(hist_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        job_id = row.get('encryptJobId') # 注意字段名要对应
                        if job_id:
                            self.seen_job_ids.add(job_id)
                print(f" 历史库加载完成，已过滤 {len(self.seen_job_ids)} 条旧数据")
            except:
                pass
        self.start_heartbeat()#启动心跳
        print("开始采集")
        consecutive_empty=0
        for page in range(1,max_pages+1):
            if getattr(self, '_stop_flag', False):
                print("收到停止信号，停止采集")
                break
            print(f"\n第{page}页，获取列表中")
            list_result=self.api_job_list(page=page,keyword=keyword)
            if not list_result:
                print(f"{page}页列表获取失败，重试1次")
                time.sleep(random.uniform(5,8))
                list_result=self.api_job_list(page=page,keyword=keyword)
                if not list_result:
                    print(f"{page}页列表仍失败，停止采集")
                    break
            job_list=list_result['zpData']['jobList']
            if not job_list:
                print("没有更多岗位了")
                break
            self.stats['page'] += 1
            self.stats['jobs_fetched'] += len(job_list)
            new_jobs = []#检测是否有新岗位
            for job in job_list:
                encrypt_job_id = job['encryptJobId']
                if encrypt_job_id not in self.seen_job_ids:
                    new_jobs.append(job)
            # 白名单过滤
            relevant_jobs = []
            filtered_count = 0
            for job in new_jobs:
                if self.is_relevant(job['jobName']):
                    relevant_jobs.append(job)
                else:
                    filtered_count += 1
                    print(f"关键词过滤: {job['jobName']}")
            # 检测连续无新相关岗位
            if len(relevant_jobs) == 0:
                consecutive_empty += 1
                print(f"本页 {len(job_list)} 个岗位全部重复或不相关，连续 {consecutive_empty} 页")
                if consecutive_empty >= 5:
                    print("连续5页无新岗位，停止采集")
                    break
                continue
            else:
                consecutive_empty = 0
                print(f"本页新岗位数: {len(relevant_jobs)}/{len(job_list)}")
            for idx,job in enumerate(relevant_jobs,1):
                encrypt_job_id = job['encryptJobId']
                security_id = job['securityId']
                job_name = job['jobName']
                salary = job['salaryDesc']
                company = job['brandName']
                self.seen_job_ids.add(encrypt_job_id)
                print(f"\n[{idx}/{len(job_list)}] {job_name}")
                print(f"       {salary} | {company}")
                job_data={
                    'encryptJobId':encrypt_job_id,
                    '工作名称':job_name,
                    "工资":salary,
                    "学历要求":job['jobDegree'],
                    "技术要求":job['skills'],
                    "工作经验要求":job['jobExperience'],
                    "工作介绍":'',
                    "工作区域":job.get('cityName', '') + job.get('areaDistrict', '') + job.get('businessDistrict', ''),
                    '工作详细地址':'',
                    "详情链接":f"https://www.zhipin.com/job_detail/{encrypt_job_id}.html",
                    "公司":company,
                    '公司阶段':job['brandStageName'],
                    '公司行业':job['brandIndustry'],
                    '公司规模':job['brandScaleName'],
                    '公司介绍':"",
                    '公司福利':job['welfareList'],
                    '公司主页':'',
                    '公司全称':'',
                    '公司简介':'',
                    '主营产品':'',
                    '公司地址':'',
                    '联系方式':'',
                    '统一社会信用代码':'',
                    '法定代表人':'',
                    '注册资本':'',
                    '成立日期':'',
                    '注册地址':'',
                    '经营范围':'',
                    '经营状态':'',
                    '纬度':'',
                    '经度':'',
                    '位置标签':''
                }
                if security_id:
                    detail_result=None
                    for retry in range(2):
                        detail_result=self.api_job_detail(security_id=security_id)
                        if detail_result:
                            break
                        if retry<1:
                            print("获取详情失败，发送紧急信号,7秒后二次重试")
                            self.urgent_event.set()
                            time.sleep(7)
                            self.get_cookie_headers()
                    if detail_result:
                        detail_data=self.parse_job_detail(detail_result)
                        job_data.update(detail_data)
                        self.stats['details_success'] += 1
                    else:
                        print("详情获取失败")
                        self.page.close()
                else:
                    print("缺少securityId")
                # 公司主页信息（缓存去重）
                try:
                    brand_id = job.get('encryptBrandId','')
                    c_info = self.fetch_company_info(brand_id)
                    for k in ('公司主页','公司全称','公司简介','主营产品','公司地址','联系方式',
                             '统一社会信用代码','法定代表人','注册资本','成立日期','注册地址','经营范围','经营状态'):
                        if c_info.get(k):
                            job_data[k] = c_info[k]
                except Exception as e:
                    print(f" 公司信息抓取异常: {e}")
                # 经纬度/位置标签来自详情API
                try:
                    for k in ('纬度','经度','位置标签'):
                        if not job_data.get(k) and detail_result:
                            dd = self.parse_job_detail(detail_result)
                            if dd.get(k):
                                job_data[k] = dd[k]
                except Exception:
                    pass
                # 从工作介绍补充联系方式
                try:
                    desc = job_data.get('工作介绍','')
                    if desc:
                        c2 = self.extract_contact(desc)
                        if c2:
                            old_c = job_data.get('联系方式','')
                            job_data['联系方式'] = (old_c + '；' + c2).strip('；') if old_c else c2
                except Exception:
                    pass
                # 公司简介/主营产品：优先用详情API的公司介绍兜底
                try:
                    comp_intro = job_data.get('公司介绍','') or ''
                    if not job_data.get('公司简介') and comp_intro:
                        job_data['公司简介'] = comp_intro[:1500]
                    if not job_data.get('主营产品') and comp_intro:
                        import re as _re
                        m = _re.search(r'(主营[^\n。]{0,100}|主营业务[^\n。]{0,100}|主打[^\n。]{0,100}|主要产品[^\n。]{0,100})', comp_intro)
                        job_data['主营产品'] = (m.group(0).strip() if m else comp_intro[:120].strip())
                except Exception:
                    pass
                self.all_jobs.append(job_data)
                # 每5条实时保存，便于及时查看结果
                if len(self.all_jobs) % 5 == 0:
                    try:
                        self.save_to_csv()
                    except Exception:
                        pass
                delay=random.uniform(5,7)#请求延迟
                time.sleep(delay)
            # 每页结束自动保存（防中途关闭丢数据）
            try:
                self.save_to_csv()
            except Exception as _e:
                print(f" 增量保存失败: {_e}")
            if target and len(self.all_jobs) >= target:
                print(f"已采集 {len(self.all_jobs)} 条，达到目标数量 {target}，停止采集")
                break
            if page<max_pages:
                print("等待翻页")
                time.sleep(random.uniform(10,15))
        print(f"   采集页数: {self.stats['page']}")
        print(f"   获取岗位: {self.stats['jobs_fetched']}")
        print(f"   详情成功: {self.stats['details_success']}")
        print(f"   实际入库: {len(self.all_jobs)}")
        return self.all_jobs
    def save_to_csv(self, filename: str = None):
        """保存为 CSV 文件（默认导出到「导出结果」文件夹）"""
        if not self.all_jobs:
            print(" 没有数据可保存")
            return
        if filename is None:
            out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '导出结果')
            os.makedirs(out_dir, exist_ok=True)
            filename = os.path.join(out_dir, 'boss_jobs.csv')
        file_exists = os.path.isfile(filename)
        start = getattr(self, '_saved_count', 0)
        new_rows = self.all_jobs[start:]
        if not new_rows:
            return
        with open(filename, 'a', encoding='utf-8-sig', newline='') as f:
            fieldnames = list(self.all_jobs[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerows(new_rows)
        self._saved_count = len(self.all_jobs)
        print(f" 数据已追加: {filename} (+{len(new_rows)})")
                
    #运行
    #运行
    def run(self):
        try:
            self.login()#登陆
            # 用户输入要采集的岗位数量
            try:
                target_str = input("请输入要采集的岗位数量（默认300，回车直接开始）: ").strip()
                target_count = int(target_str) if target_str else 300
            except ValueError:
                print("输入无效，使用默认值300")
                target_count = 300
            target_count = max(10, min(target_count, 2000))
            # 每页约30条但有关键词过滤，按目标数量换算页数
            import math
            max_pages = max(3, math.ceil(target_count / 15) + 2)
            print(f"目标数量: {target_count} 条，预计采集 {max_pages} 页")
            self.crawl(max_pages=max_pages, target=target_count)#设置关键词、页数和目标数量
            if self.all_jobs:
                self.save_to_csv()
        except KeyboardInterrupt:
            print("\\n 用户中断")
            self.save_to_csv()
        except Exception as e:
            print(f" 程序异常: {e}")
            import traceback
            traceback.print_exc()
            self.save_to_csv()
        finally:
            # 清理
            try:
                self.page.quit()
            except:
                pass
            print(" 程序结束")

if __name__ == "__main__":
    spider = BossDP()
    spider.run()
