
import requests
import json
import jsonpath
import pymongo
import time
import random

from itertools import product
from lxml import etree


class AHSSpider(object):
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:39.0) Gecko/20100101 Firefox/39.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }
        self.start_url = 'https://www.aihuishou.com'
        # mongodb参数
        self.mongo_host = '127.0.0.1'
        self.mongo_port = 27017
        self.mongo_cli = pymongo.MongoClient(host=self.mongo_host, port=self.mongo_port)
        self.mongo_db = self.mongo_cli['aihuishou']

    def start_request(self):
        response = requests.get(self.start_url, headers=self.headers)
        return response

    def parse_category(self, respone):
        html = etree.HTML(respone.text)
        # 解析分类的url
        category_urls = html.xpath(r'//div[@id="category-pop"]/ul/li//a/@href')
        return category_urls

    def send_request(self, url):
        response = requests.get(url, headers=self.headers)
        return response

    def parse_brand(self, resposne):
        """
        解析品牌分类url
        :param resposne:
        :return: 返回品牌分类的url列表
        """
        html = etree.HTML(resposne.text)
        # 解析手机品牌
        brands_urls = html.xpath(r'//div[@class="main-right"]/ul/li/a/@href')
        return brands_urls

    def parse_products(self, response):
        """
        解析手机型号urls
        :param response:
        :return:手机型号的url列表，和下一页的url
        """
        html = etree.HTML(response.text)
        product_urls_list = []
        # 解析手机型号
        product_urls = html.xpath(r'//div[@class="product-list-wrapper"]/ul/li/a/@href')
        try:
            next_page = html.xpath(r'//div[@class="product-list-pager"]/a[@class="next no_hover"]/@href')[0]
        except Exception as e:
            print('-----没有下一页了------')
            next_page = False

        while next_page:
            r = self.send_request(next_page)
            html = etree.HTML(r.text)
            product_urls += html.xpath(r'//div[@class="product-list-wrapper"]/ul/li/a/@href')
            try:
                next_page = html.xpath(r'//div[@class="product-list-pager"]/a[@class="next no_hover"]/@href')
            except Exception as e:
                next_page = False
                print('-----没有下一页了！！-----')
                print(e)
        return product_urls

    def parse_params(self, response):
        """
        解析查询价格需要的参数，AuctionProductId, ProductModelId, PriceUnits
        :param response:
        :return: 请求价格的参数, pid, mid, price_units
        """
        html = etree.HTML(response.text)

        # 解析各模块的data-id
        # 基本参数
        base_data_ids = html.xpath(r'//div[@id="group-property"]/@data-sku-property-value-ids')[0]
        # 解析pid
        pid = html.xpath(r'//div[@class="right"]/div[contains(@class, "footer")]/a/@data-pid')[0]
        # 解析mid
        try:
            mid = html.xpath(r'//div[@class="right"]/div[contains(@class, "footer")]/a/@data-mid')[0]
        except Exception as e:
            mid = ''
            print(e)
        data_id_elements = html.xpath(r'//div[contains(@class, "select-property")]/dl')
        data_ids = []
        for element in data_id_elements:
            data_ids.append(element.xpath(r'./dd/ul/li/@data-id'))

        # 去除data_ids中为空的列表
        for each in data_ids:
            if each == []:
                data_ids.remove(each)

        # 所有可能组合的price_units
        data_ids_str = ''  # 用来将各列表放入字符串中，'[],[],[]'的形式
        for each in data_ids:
            if each != data_ids[-1]:
                data_ids_str += str(each) + ','
            else:
                data_ids_str += str(each)

        price_units_list = list(product(*eval(data_ids_str)))
        # 没有最后一项时的price_units组合
        data_ids_str2 = ''
        for each in data_ids[:-1]:
            if each != data_ids[-2]:
                data_ids_str2 += str(each) + ','
            else:
                data_ids_str2 += str(each)
        price_units_list2 = list(product(*eval(data_ids_str2)))
        # 整合到一起
        price_units_list += price_units_list2
        price_units_list3 = [';'.join(i) for i in price_units_list]

        return pid, mid, price_units_list3

    def send_post_request(self, pid, mid, price_units_list):
        """
        模拟发送post请求，响应是重定向的url
        :param pid:
        :param mid:
        :param price_units_list:
        :return:
        """
        url = 'http://www.aihuishou.com/userinquiry/create'
        for each_units in price_units_list:
            data = {
                'AuctionProductId': pid,
                'ProductModelId': mid,
                'PriceUnits': each_units
            }
            r = requests.post(url, data=data, headers=self.headers)
            time.sleep(random.randint(2, 4))

            print(r.text)
            # 解析响应中的重定向url
            self.parse_price_url(r)

    def parse_price_url(self, resposne):
        """解析重定向url， 构造价格的url"""
        jsonobj = json.loads(resposne.text)
        price_url = jsonobj['data']['redirectUrl']
        # price_url 的格式是/pc/index.html#/inquiry/6534929115267980857
        # 截取url的inquiry后面的部分6534929115267980857
        key = price_url.split('/')[-1]
        print(key)
        # 构造请求价格json的url'https://www.aihuishou.com/portal-api/inquiry/9138426214174445089'
        price_url = 'https://www.aihuishou.com/portal-api/inquiry/' + key
        # 发送请求
        r = self.send_request(price_url)
        time.sleep(random.randint(2, 4))

        print(r.text)
        self.parse_price(r)

    def parse_price(self, response):
        """解析价格相关的信息"""
        jsonobj = json.loads(response.text)
        price = jsonpath.jsonpath(jsonobj, r'$.data.amount')
        top_recycle_price = jsonpath.jsonpath(jsonobj, r'$.data.product.topRecyclePrice')
        product_id = jsonpath.jsonpath(jsonobj, r'$.data.product.productId')
        product_name = jsonpath.jsonpath(jsonobj, r'$.data.product.productName')
        inquiry_values = jsonpath.jsonpath(jsonobj, r'$.data.inquiryValues')
        inquiry_value_list = []
        for each in inquiry_values:
            inquiry_value_list.append(each['name'])

        item = {
            'price': price,
            'top_recycle_price': top_recycle_price,
            'product_id': product_id,
            'product_name': product_name,
            'inquiry_values': inquiry_value_list
        }

        # return item
        # 保存数据到mongodb
        self.mongo_db.data.insert(item)


def schedule():
    """调度器"""
    worker = AHSSpider()
    r = worker.start_request()

    # print(r.text)
    # 解析产品大分类
    category_urls = worker.parse_category(r)
    print(category_urls)
    # 爬取各个分类，后续可以对此部分优化, 例如可以用多线程爬取各个分类下的商品
    for category_url in category_urls:
        # 构造请求url
        category_url = worker.start_url + category_url
        r = worker.send_request(category_url)
        time.sleep(random.randint(2, 4))
        # 解析大类下的品牌
        brand_urls = worker.parse_brand(r)
        # 解析品牌下的产品
        for brand_url in brand_urls:
            # 构造请求url
            brand_url = worker.start_url + brand_url
            r = worker.send_request(brand_url)
            time.sleep(random.randint(2, 4))
            product_urls = worker.parse_products(r)
            # 解析每个产品下的价格信息
            for product_url in product_urls:
                product_url = worker.start_url + product_url
                r = worker.send_request(product_url)
                time.sleep(random.randint(2, 4))
                pid, mid, price_unites_list = worker.parse_params(r)
                # 解析并保存数据
                worker.send_post_request(pid, mid, price_unites_list)


if __name__ == '__main__':
    schedule()
