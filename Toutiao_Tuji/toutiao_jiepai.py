import json
import os
from hashlib import md5
import pymongo
import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException
from urllib.parse import urlencode
import re
from config import *
from multiprocessing import Pool

client = pymongo.MongoClient(MONGO_URL, connect=False)
db = client[MONGO_DB]

headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:56.0) Gecko/20100101 Firefox/56.0',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Connection': 'Keep-Alive',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }

#获取页面信息
def get_page_index(offset, keyword):
    #定义headers头

    data = {
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': '20',
        'cur_tab': 3,
        'from': 'gallery'
    }

    url = 'https://www.toutiao.com/search_content/?' + urlencode(data)
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('请求失败')
        return None

#索引
def parse_page_index(html):
    data = json.loads(html)
    if data and 'data' in data.keys():
        for item in data.get('data'):
            yield item.get('article_url')


#获取详情页信息
def get_page_detail(url):
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('请求详情页错误', url)
        return None

# 获取页面详情
def parse_page_detail(html, url):
    soup = BeautifulSoup(html, 'lxml')
    # 标题正则对象
    title_pattern = re.compile('title:(.*?),', re.S)
    # 查找
    result_title = re.search(title_pattern, html)
    if result_title:
        title_data = result_title.group(1)
        # print(title_data)

    # 图片正则表达式对象
    image_pattern = re.compile('gallery: JSON.parse\("(.*?)"\)', re.S)
    result_image = re.search(image_pattern, html)
    # 替换不需要的数据
    jsonImage = re.sub(r'\\{1,2}','',result_image.group(1))
    if result_image:
        image_data = json.loads(jsonImage)
        # print(result_image.group(1)) # 测试

        if image_data and 'sub_images' in image_data.keys():
            sub_images = image_data.get('sub_images')
            # print(sub_images) # 测试
            # 装换成数组
            images = [item.get('url') for item in sub_images]
            # 下载图片
            for image in images: download_image(image)
            return {
                'title': title_data,
                'url': url,
                'images': images
            }

# 下载图片
def download_image(url):
    print('正在下载：', url)
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            save_image(response.content)
        return None
    except RequestException:
        print('请求图片错误', url)
        return None

# 存储图片
def save_image(content):
    # 设置路径
    file_path = '{0}/{1}.{2}'.format(os.getcwd(), md5(content).hexdigest(), 'jpg')
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as f:
            f.write(content)
            f.close()

# 存储到mongoDB
def save_to_mongo(result):
    if db[MONGO_TABLE].insert(result):
        print('存储成功', result)
        return True
    return False

def main(offset):
    html = get_page_index(offset, KEYWORD)
    for url in parse_page_index(html):
        html = get_page_detail(url)
        if html:
            result = parse_page_detail(html, url)
            if result: save_to_mongo(result)

if __name__ == '__main__':
    groups = [x*20 for x in range(GROUP_START, GROUP_END+1)]
    # 开启多线程下载
    pool = Pool()
    pool.map(main, groups)
    # main()
