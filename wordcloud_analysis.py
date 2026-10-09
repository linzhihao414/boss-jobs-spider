import pandas as pd
import jieba
from collections import Counter
from wordcloud import WordCloud
import matplotlib.pyplot as plt

df=pd.read_csv(r'boss_jobs_cleaned.csv',encoding='utf-8')
des=df['工作介绍'].tolist()
with open(r'stopwords_hit.txt',encoding='utf-8')as f:
    stopwords=set(f.read().strip().split('\n'))
#清理无关词
job_stopwords = {'负责', '要求', '具备', '熟悉', '工作', '设计', '开发', 
                 '相关', '能够', '完成', '进行', '参与', '协助', '配合',
                 '根据', '按照', '以及', '或者', '具有', '良好', '优秀',
                 '独立', '一定', '经验', '能力', '优先', '包括', '职责', 
                 '任务', '岗位', '职位', '描述', '介绍', '公司', '我们', 
                 '团队', '技术', '系统', '平台', '业务', '项目', '问题',
                 '解决', '处理', '分析', '需要', '需求', '使用', '应用', 
                 '支持', '维护', '优化', '提升', '实现','爬虫','数据',
                 '采集','抓取','以上学历','确保','精通','框架','本科',
                 '硕士','熟练掌握','熟练','以上','任职','主流','了解'
                 ,'常见','岗位职责','掌握','各类','网站','方案','策略'
                 ,'监控','研究','基础','常用','复杂','至少','语言'}
stopwords.update(job_stopwords)
#设置白名单防止被乱拆分
white_list=['Python','分布式','Mysql','Linux','Docker']
for i in white_list:
    jieba.add_word(i)
all_words=[]
for d in des:
    words=jieba.lcut(str(d))
    for w in words:
        if w not in stopwords and len(w)>1:
            all_words.append(w)
word_counts=Counter(all_words)
for word,count in word_counts.most_common(50):
    print(f'{word}:{count}')
#构建词云  
wc=WordCloud(
    font_path='msyh.ttc',
    background_color='white',
    max_words=50,
    width=1024,
    height=1024,
    random_state=42,
    colormap='viridis'
)

wc.generate_from_frequencies(word_counts)

plt.imshow(wc,interpolation='bilinear')
plt.axis('off')
plt.show()
wc.to_file('技能词云.png')
