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
import concurrent.futures
from urllib.parse import quote, unquote
Config={
    "start_url":'https://www.zhipin.com/web/geek/jobs?city=101210100&query=数据采集',
    "heart_time":15,#每4个详情就需要刷新一次，每个详情花3-5秒访问
    "keyword":quote('数据采集')
}
class BossDP:
    def __init__(self):
        self.cookie_lock=threading.Lock()#多线程加上线程锁
        self.urgent_event=threading.Event()#设置紧急心跳信号
        co=ChromiumOptions()
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
        with self.cookie_lock:
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
                    'referer': f'https://www.zhipin.com/web/geek/jobs?city=101210100&query={Config["keyword"]}',
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
            if job_list:
                jobs=job_list.eles('.job-card-box')
            print(f"提取到{len(jobs)}个岗位卡片")
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
        f"city=101210100&"
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
        return{
            "工作介绍":job_info['postDescription'],
            "工作详细地址":job_info['address'],
            "公司介绍":brand_info['introduce']
        }
    def is_relevant(self,job_name):
        whitelist = [
        '爬虫', 
        '数据采集', '数据抓取', '数据获取',
        '逆向', '反爬','采集','RPA','rpa','Python','python'
    ]
        for kw in whitelist:
            if kw.lower() in job_name.lower():
                return True
        return False

    def get_one_detail(self,job):
        time.slee[(random.uniform(3,5))]
        encrypt_job_id = job['encryptJobId']
        security_id = job['securityId']
        job_name = job['jobName']
        salary = job['salaryDesc']
        company = job['brandName']
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
            '公司福利':job['welfareList']
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
                self.seen_job_ids.add(encrypt_job_id)
                return job_data
            else:
                print("详情获取失败")
                return None
        else:
            print("缺少securityId")
            return None
    
    def crawl_concurrent(self,max_pages,keyword:str=Config['keyword'],max_workers=3):
        if os.path.exists("boss_jobs.csv"):
            try:
                with open("boss_jobs.csv", 'r', encoding='utf-8-sig') as f:
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
            print(f"\n第{page}页，获取列表中")
            list_result=self.api_job_list(page=page,keyword=keyword)
            if not list_result:
                print(f"{page}页列表获取失败")
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
                    print(f"白名单过滤: {job['jobName']}")
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
            print(f"开始并发采集,并发数{max_workers}")
            page_success=0#并发采集成功数
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)as executor:
                future_to_job={
                    executor.submit(self.get_one_detail,job):job
                    for job in relevant_jobs
                }
                for future in concurrent.futures.as_completed(future_to_job):
                    job=future_to_job[future]
                    try:
                        result=future.result(timeout=30)
                        if result:
                            self.all_jobs.append(result)
                            page_success+=1
                            print(f"[{page_success}/{len(relevant_jobs)}] {result['工作名称']} 详情获取成功")
                    except Exception as e:
                        print(f"{job['jobName']}处理异常:{e}")
            self.stats['details_success']+=page_success
            if page<max_pages:
                wait_time=random.uniform(10,15)
                print(f"等待{wait_time}秒后翻页")
                time.sleep(wait_time)
               

        print(f"   采集页数: {self.stats['page']}")
        print(f"   获取岗位: {self.stats['jobs_fetched']}")
        print(f"   详情成功: {self.stats['details_success']}")
        print(f"   实际入库: {len(self.all_jobs)}")
        return self.all_jobs
    def save_to_csv(self, filename: str = "boss_jobs.csv"):
        """保存为 CSV 文件"""
        if not self.all_jobs:
            print(" 没有数据可保存")
            return
        file_exists = os.path.isfile(filename)
        with open(filename, 'a', encoding='utf-8-sig', newline='') as f:
            fieldnames = list(self.all_jobs[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            
            writer.writerows(self.all_jobs)
        print(f" 数据已追加: {filename}")
                
    #运行
    def run(self):
        try:
            self.login()#登陆
            
            self.crawl_concurrent(max_pages=30)#设置关键词和页数
            if self.all_jobs:
                self.save_to_csv("boss_jobs.csv")       
        except KeyboardInterrupt:
            print("\n 用户中断")
            self.save_to_csv("boss_jobs.csv")
        except Exception as e:
            print(f" 程序异常: {e}")
            import traceback
            traceback.print_exc()
            self.save_to_csv("boss_jobs.csv")
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