# -*- coding: utf-8 -*-
import json

import scrapy
from scrapy import spider, Request

from zhihuuser.items import UserItem


class ZhihuSpider(scrapy.Spider):
    name = 'zhihu'
    allowed_domains = ['www.zhihu.com']
    start_urls = ['http://www.zhihu.com/']

    start_user = 'evanyou'

    # 用户信息
    user_url = 'https://www.zhihu.com/api/v4/members/{user}?include={include}'
    user_query = 'allow_message,is_followed,is_following,is_org,is_blocking,employments,answer_count,follower_count,articles_count,gender,badge[?(type=best_answerer)].topics'

    # followee信息-他关注的人
    follower_url = 'https://www.zhihu.com/api/v4/members/{user}/followees?include={include}&offset={offset}&limit={limit}'
    follower_query = 'data[*].answer_count,articles_count,gender,follower_count,is_followed,is_following,badge[?(type=best_answerer)].topics'

    # followers信息-关注他的人的信息
    followers_url = 'https://www.zhihu.com/api/v4/members/{user}/followers?include={include}&offset={offset}&limit={limit}'
    followers_query = 'data[*].answer_count,articles_count,gender,follower_count,is_followed,is_following,badge[?(type=best_answerer)].topics'

    def start_requests(self):
        # url = 'https://www.zhihu.com/api/v4/members/ji-xu-zhe-zhang?include=allow_message%2Cis_followed%2Cis_following%2Cis_org%2Cis_blocking%2Cemployments%2Canswer_count%2Cfollower_count%2Carticles_count%2Cgender%2Cbadge%5B%3F(type%3Dbest_answerer)%5D.topics'
        # url = 'https://www.zhihu.com/api/v4/members/excited-vczh/followees?include=data%5B*%5D.answer_count%2Carticles_count%2Cgender%2Cfollower_count%2Cis_followed%2Cis_following%2Cbadge%5B%3F(type%3Dbest_answerer)%5D.topics&offset=60&limit=20'

        # 获取start_user的信息
        yield Request(self.user_url.format(user=self.start_user, include=self.user_query), callback=self.parse_user)

        # 获取start_user的followee的信息
        yield Request(self.follower_url.format(user=self.start_user, include=self.follower_query, offset=0, limit=20), callback=self.parse_follows)

        # 获取start_user的关注者信息
        yield Request(self.followers_url.format(user=self.start_user, include=self.followers_query, offset=0, limit=20), callback=self.parse_followers)

    def parse_user(self, response):
        """
        :function: 解析用户
        :param response: response数据
        :return: 用户数据
        """
        # 获取用户信息
        result = json.loads(response.text)
        item = UserItem()
        for field in item.fields:
            if field in result.keys():
                item[field] = result.get(field)
        yield item

        # 通过递归解析其他用户的follow
        yield Request(self.follower_url.format(user=result.get('url_token'), include=self.follower_query, limit=20, offset=0), callback=self.parse_follows)

        # 通过关注他的人解析其他用户
        yield Request(self.followers_url.format(user=result.get('url_token'), include=self.follower_query, limit=20, offset=0), callback=self.parse_followers)


    def parse_follows(self, response):
        """
        :function: 解析follows
        :param response: 关注列表
        :return: 关注列表信息
        """
        result = json.loads(response.text)
        if 'data' in result.keys():
            for result in result.get('data'):
                yield Request(self.user_url.format(user=result.get('url_token'), include=self.user_query), callback=self.parse_user)

        # 获取分页信息
        if 'paging' in result.keys() and result.get('paging').get('is_end') == False:
            next_page = result.get('paging').get('next')
            yield Request(next_page, callback=self.parse_follows)


    def parse_followers(self, response):
        """
        :function: 解析followers
        :param response: 关注列表
        :return: 关注他的列表信息
        """
        result = json.loads(response.text)
        if 'data' in result.keys():
            for result in result.get('data'):
                yield Request(self.user_url.format(user=result.get('url_token'), include=self.user_query), callback=self.parse_user)

        # 获取分页信息
        if 'paging' in result.keys() and result.get('paging').get('is_end') == False:
            next_page = result.get('paging').get('next')
            yield Request(next_page, callback=self.parse_followers)
