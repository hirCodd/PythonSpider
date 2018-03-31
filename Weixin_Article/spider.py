from urllib.parse import urlencode
import pymongo
import requests
from lxml.etree import XMLSyntaxError
from requests.exceptions import ConnectionError
from pyquery import PyQuery as pq
from config import *

# mongo连接信息
client = pymongo.MongoClient(MONGO_URL)
db = client[MONGO_DB]

base_url = 'http://weixin.sogou.com/weixin?'

# 登录之后的cookie信息,用你自己的代替
Cookie = '######'

# cookie 如果过期自动更换即可
headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Cookie': Cookie,
    'Host': 'weixin.sogou.com',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36'
}


proxy = None

def get_proxy():
    """
    :function: 获取代理
    :return: 代理ip
    """
    try:
        response = requests.get(PROXY_POOL_URL)
        if response.status_code == 200:
            return response.text
        return None
    except ConnectionError:
        return None

def get_html(url, count=1):
    """
    :function: 设置代理，若本机不能请求数据，就使用代理池提供的代理请求数据，并且将请求到的html页面数据返回
    :param url: 获取文章的url=base+other_info拼接而成
    :param count: proxy连接数量
    :return: 1.200：网页文本
             2.302: 再次请求
    """
    print('Crawling', url)
    print('Trying Count', count)
    global proxy
    if count >= MAX_COUNT:
        print('Tried Too Many Counts')
        return None
    try:
        if proxy:
            # 拼接代理
            proxies = {
                'http://': 'http://' + proxy
            }
            # 通过代理请求数据
            response = requests.get(url, allow_redirects=False, headers=headers, proxies=proxies)
        else:
            # 通过本机ip请求数据
            response = requests.get(url, allow_redirects=False, headers=headers)
        if response.status_code == 200:
            return response.text
        # 被反之后的处置
        if response.status_code == 302:
            # 设置代理
            print('302')
            # 设置代理http
            proxy = get_proxy()
            if proxy:
                print('Using Proxy', proxy)
                # 递归重新请求页面
                return get_html(url)
            else:
                # 无代理则返回空
                print('Get Proxy Failed')
                return None
    except ConnectionError as e:
        # 确保没有死循环
        print('Error Occurred', e.args)
        proxy = get_proxy()
        # 多次请求代理无效直接down
        count += 1
        return get_html(url, count)


def get_index(keyword, page):
    """
    :function: 获得搜索所得的索引页面
    :param keyword: 搜索关键字
    :param page: 搜索产生的页面
    :return: 通过url返回的页面
    """
    data = {
        'query': keyword,
        'type': 2,
        'page': page,
        'ie': 'utf8'
    }
    queries = urlencode(data)
    url = base_url + queries
    # 调用get_html
    html = get_html(url)
    return html


def parse_index(html):
    """
    :function: 通过pyquery解析获得href
    :param html: 通过pq解析页面
    :return: 解析得到的href
    """
    doc = pq(html)
    items = doc('.news-box .news-list li .txt-box h3 a').items()
    for item in items:
        yield item.attr('href')


def get_detail(url):
    """
    :function: 通过url地址解析获得页面文字(通过微信文章的url获得文章所有信息)
    :param url: weixin_url
    :return: weixin页面所有文字信息
    """
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        return None
    except ConnectionError:
        return None

def parse_detail(html):
    """
    :function: 通过微信html页面提取所需要的关键信息
    :param html: 微信的html页面
    :return: 我们所需要关键信息
    """
    try:
        doc = pq(html)
        title = doc('.rich_media_title').text()
        content = doc('.rich_media_content').text().replace('\n', '')
        date = doc('#post-date').text()
        nickname = doc('#js_profile_qrcode > div > strong').text()
        wechat = doc('#js_profile_qrcode > div > p:nth-child(3) > span').text()
        return {
            'title': title,
            'content': content,
            'date': date,
            'nickname': nickname,
            'wechat': wechat
        }
    except XMLSyntaxError:
        return None

def save_to_mongo(data):
    """
    :function: 判断是否存在文章标题更新数据库
    :param data: 文章关键信息
    :return: 存储了那些信息
    """
    if db[MONGO_TABLE].update({'title': data['title']}, {'$set': data}, True):
        print('Saved To Mongo', data['title'])
    else:
        print('Saved To Mongo Failed', data['title'])

def main():
    for page in range(1, 10):
        # 通过关键字提取页面1-9的页面
        html = get_index(KEYWORD, page)
        if html:
            # 通过页面解析获得url
            article_urls = parse_index(html)
            for article_url in article_urls:
                # 通过url获取文章页面文字
                article_html = get_detail(article_url)
                if article_html:
                    # 解析文章页面数据
                    article_data = parse_detail(article_html)
                    # 输出文章data
                    print(article_data)
                    if article_data:
                        save_to_mongo(article_data)

if __name__ == '__main__':
    main()

