# -*- coding: utf-8 -*-
"""Simulate real flow: open page, wait, sync cookies, call list API"""
import os, sys, time, random
sys.path.insert(0, r"D:\boss_jobs_spider-main")
os.chdir(r"D:\boss_jobs_spider-main")

import boss_spider as bs

spider = bs.BossDP()
try:
    # Open BOSS search page (like login() but no input)
    spider.page.get(bs.Config['start_url'])
    print("页面已打开，等待登录态恢复...")
    time.sleep(10)
    # Simulate user pressing Enter
    spider.get_cookie_headers()
    print(f"cookies数量: {len(spider.current_cookies)}")
    # Try list API page 1
    result = spider.api_job_list(page=1)
    if result:
        zp = result['zpData']
        jobs = zp.get('jobList', [])
        print(f"列表接口成功！本页岗位数: {len(jobs)}")
        for j in jobs[:3]:
            print(f"  - {j['jobName']} | {j['salaryDesc']} | {j['brandName']} | brandId={j.get('encryptBrandId','')[:8]}")
    else:
        print("列表接口返回失败")
finally:
    try:
        spider.page.quit()
    except:
        pass
print("DONE")
