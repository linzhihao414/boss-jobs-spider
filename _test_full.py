# -*- coding: utf-8 -*-
"""Full flow test: login state -> crawl 1 page -> save to 导出结果"""
import os, sys, time
sys.path.insert(0, r"D:\boss_jobs_spider-main")
os.chdir(r"D:\boss_jobs_spider-main")

import boss_spider as bs

spider = bs.BossDP()
try:
    spider.page.get(bs.Config['start_url'])
    print("等待登录态恢复...")
    time.sleep(10)
    spider.get_cookie_headers()
    print(f"cookies: {len(spider.current_cookies)}")
    spider.crawl(max_pages=3)
    spider.save_to_csv()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '导出结果', 'boss_jobs.csv')
    print(f"导出文件: {out}")
    print(f"文件存在: {os.path.exists(out)}")
    if os.path.exists(out):
        print(f"文件大小: {os.path.getsize(out)} bytes")
finally:
    try:
        spider.page.quit()
    except:
        pass
print("DONE")
