# -*- coding: utf-8 -*-
"""Probe: detail API fields + company page business info"""
import os, sys, time, json
sys.path.insert(0, r"D:\boss_jobs_spider-main")
os.chdir(r"D:\boss_jobs_spider-main")

import boss_spider as bs

spider = bs.BossDP()
try:
    spider.page.get(bs.Config['start_url'])
    print("等待页面加载...")
    time.sleep(8)
    spider.get_cookie_headers()
    # Get one job
    result = spider.api_job_list(page=1)
    if not result:
        print("列表失败")
        sys.exit(1)
    jobs = result['zpData']['jobList']
    print(f"列表OK，{len(jobs)}条")
    j = jobs[0]
    print(f"岗位: {j['jobName']} | 公司: {j['brandName']} | brandId: {j.get('encryptBrandId','')}")
    # Detail API full keys
    sec = j.get('securityId','')
    detail = spider.api_job_detail(sec)
    if detail:
        zp = detail['zpData']
        ji = zp.get('jobInfo', {})
        bc = zp.get('brandComInfo', {})
        print("\n=== jobInfo keys ===")
        print(sorted(ji.keys()))
        print("\n=== brandComInfo keys ===")
        print(sorted(bc.keys()))
        print("\n=== jobInfo['address'] ===")
        print(ji.get('address', ''))
        if 'brandComInfo' in zp:
            print("\n=== brandComInfo sample ===")
            for k in ['brandName','introduce','more','companyInfo']:
                if k in bc:
                    v = bc[k]
                    print(f"{k}: {str(v)[:200]}")
        print("\n=== zpData keys ===")
        print(sorted(zp.keys()))
    # Company page: check business info presence
    bid = j.get('encryptBrandId','')
    if bid:
        spider.page.get(f"https://www.zhipin.com/gongsi/{bid}.html")
        time.sleep(5)
        html = spider.page.html
        print(f"\n=== 公司页工商信息探测 ({bid}) ===")
        for kw in ['统一社会信用代码','工商信息','法定代表人','注册资本','成立','注册地址','经营范围','经营状态']:
            print(f"  {kw}: {'FOUND' if kw in html else 'no'}")
finally:
    try:
        spider.page.quit()
    except:
        pass
print("\nDONE")
