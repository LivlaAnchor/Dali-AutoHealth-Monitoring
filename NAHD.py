# -*- coding: UTF-8 -*-
# 声明：本项目仅供研究学习用途，任何企图用于非法盈利，损害，破坏其他计算机，自行承担法律责任！
# 若有侵权和不妥行为，请与作者联系mail: xingyuguan@foxmail.com

import base64
import concurrent
import smtplib
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from email.mime.text import MIMEText

import pymysql
import requests

# -------------------------------------------------------
# *********************配置文件***************************
# 配置日志文件位置，支持在linux 和 windows上
if sys.platform.startswith('linux'):
    logfile = r''
else:
    logfile = r''

# 配置每日包的token
time_token = [
    'ff8080817f8b5c9e017fdf5314b13a7e',
    'ff8080817f8b5da8017fdf53e9af3ac3',
    'ff8080817f8b5da8017fdf53e9af3ac3'
]

# 配置发送者邮箱和授权码，授权码百度怎么获取（注：不可泄露授权码，危险）
mail_info = {
    'sender_email': '',
    'Authorization_code': '',
}

# 配置每数据库信息
# 若不使用数据库，则看下方
# 数据库键形式
# user_id   QQ_number   order_num(仅用于划定优先级)
database_info = {
    'host': '',         # 服务器ip
    'port': '',                  # 数据库端口
    'user': '',              # 数据库用户
    'password': '',  # 数据库密码
    'db': ''                 # 数据库名
}


# 若不使用数据库，则新建一个名为users的列表 ，写入[学号, QQ, 优先级（随便写）]
# 并注释掉main函数的第一行即可
# users = [
#    ['2019111000', '1234567', 1],
#    ['2019111001', '12345678', 2],
#    ['2019111001', '12345678', 3],
# ]

# *********************配置文件***************************
# -------------------------------------------------------

# -----自定义异常
# 打卡已完成 今日打卡已完成
class TaskOverError(Exception):
    def __init__(self, error_info):
        super(TaskOverError, self).__init__(error_info)
        self.error_info = error_info

    def __str__(self):
        return self.error_info


# 目标服务器响应错误
class ResponseError(Exception):
    def __init__(self, error_info):
        super(ResponseError, self).__init__(error_info)
        self.error_info = error_info

    def __str__(self):
        return self.error_info


# 目标服务器严重的未知错误
class UnknownError(Exception):
    def __init__(self, error_info):
        super(UnknownError, self).__init__(error_info)
        self.error_info = error_info

    def __str__(self):
        return self.error_info


# 日志书写 + 邮件提醒
class LogWriter:
    def __init__(self):
        self.error = ""  # 如果出现此类现象，立即发送邮件
        self.t = time.localtime()
        now_order = str(self.t.tm_hour) + "h"
        self.nowTime = time.strftime('%Y-%m-%d', self.t) + ' ' + now_order

    def info_log(self, content):
        with open(logfile + self.nowTime + '.txt', 'a', encoding='utf-8') as file:
            file.write(self.nowTime + ' info: ' + content + '\n')

    def error_log(self, error):
        self.error += error
        with open(logfile + self.nowTime + '.txt', 'a', encoding='utf-8') as file:
            file.write(self.nowTime + ' info: ' + error + '\n')

    def mail_send(self, receiver, title, message):
        sender = mail_info.get('sender_email')  # 发件人的地址
        password = mail_info.get('Authorization_code')  # 在邮箱中获取的授权码
        server = smtplib.SMTP_SSL("smtp.qq.com", 465)  # 配置qq邮箱的smtp服务器地址
        server.login(sender, password)  # 登录
        message = MIMEText(message, 'plain', 'utf-8')  # 邮件内容设置
        message['Subject'] = title  # 邮件标题设置
        message['From'] = sender  # 发件人信息
        message['To'] = receiver  # 收件人信息
        try:
            server.sendmail(sender, receiver, message.as_string())
            self.info_log(receiver + " 邮件发送成功！")
            # print('发送成功')
            server.quit()
        except:
            self.error_log("邮件发送失败" + " 目标：" + receiver)
            # print("发送失败" + str(e))

    def send_all_error(self):
        if self.error != '':
            self.mail_send('527984256@qq.com', self.nowTime + '严重错误', self.error)


# 单例化日志对象
log = LogWriter()


# 获取任务类
class UserTask:
    def __init__(self):
        self.mysql_conn = pymysql.connect(host=database_info.get('host'),
                                          port=database_info.get('port'),
                                          user=database_info.get('user'),
                                          password=database_info.get('password'),
                                          db=database_info.get('db'))
        self.users = ()
        sql = "SELECT * FROM task order by order_num"
        try:
            with self.mysql_conn.cursor() as cursor:
                cursor.execute(sql)
                self.users = cursor.fetchall()
                log.info_log("任务获取成功!")
        except Exception as e:
            log.error_log("任务获取失败!\n原因\n" + str(e))
        finally:
            self.mysql_conn.close()


# 打卡主类
class mainTask:

    @staticmethod
    def which_time():
        hour = int(log.t.tm_hour)
        if 8 <= hour < 12:
            return 'morning'
        elif 14 <= hour < 17:
            return 'afternoon'
        else:
            return 'evening'

    @staticmethod
    def taskRun(user):
        log.info_log(user[0] + "进入打卡")
        # 获取打卡id
        now_time = mainTask.which_time()
        if now_time == 'morning':
            # now_time = '4a4b90aa73fad84c017411601830099d'
            now_time = time_token[0]
        elif now_time == 'afternoon':
            # now_time = '4a4b90aa73fad84c0174117a761409b1'
            now_time = time_token[1]
        elif now_time == 'evening':
            # now_time = '4a4b90aa73faf66a0174116ae01b0a14'
            now_time = time_token[2]
        else:
            raise Exception("time is error")

        # 获取token登录
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Safari/537.36 Edg/99.0.1150.46",
        }
        url = "http://202.203.16.42/"
        response = requests.get(url, headers=headers)
        info = response.cookies.get_dict()
        # print(response.cookies.get_dict())
        log.info_log(user[0] + "info:" + str(info))
        if len(info) == 0:
            log.error_log(user[0] + "cookie空")
            raise Exception("cookie空")
        headers = {
            "Host": "202.203.16.42",
            "Connection": "close",
            "Content-Length": "112",
            "Accept": "text/html, */*; q=0.01",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Safari/537.36 Edg/99.0.1150.46",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "http://202.203.16.42",
            "Referer": "http://202.203.16.42/",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Cookie": "menuVisible=0; JSESSIONID={0}; username={1}".format(info.get('JSESSIONID'), user[0])
        }
        url = "http://202.203.16.42//login/Login.htm"
        data = {
            "username": base64.b64encode(user[0].encode('utf8')),
            "password": base64.b64encode(str("@c" + user[0]).encode('utf8')),
            "verification": "",
            "token": info.get('token')
        }
        # 此处收到会重定向，不用管
        response = requests.post(url, data=data, headers=headers).text
        log.info_log(user[0] + "已登录,状态:" + response)

        # 验证是否需要打卡
        headers = {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Content-Length": "61",
            "Host": "202.203.16.42",
            "Origin": "http://202.203.16.42",
            "Referer": "http://202.203.16.42/webApp/xuegong/index.html",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.60 Safari/537.36 Edg/100.0.1185.29",
            "Connection": "close",
            "Cookie": "menuVisible=0; JSESSIONID={0}; username={1}".format(info.get('JSESSIONID'), user[0])
        }
        url = "http://202.203.16.42/syt/zzapply/checkrestrict.htm"
        data = {
            "xmid": now_time,
            "pdnf": "2020",
            "type": "XSFXTWJC",
        }
        test_response = requests.post(url, data=data, headers=headers).text
        if test_response == '今日已经申请':
            raise TaskOverError(user[0] + '测试结果：已完成')
        else:
            log.info_log(user[0] + '测试结果：未完成')

        # 发送打卡包
        headers = {
            "Host": "202.203.16.42",
            "Connection": "close",
            "Content-Length": "392",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Safari/537.36 Edg/99.0.1150.46",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "http://202.203.16.42",
            "Referer": "http://202.203.16.42/webApp/xuegong/index.html",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Cookie": "menuVisible=0; JSESSIONID={0}; username={1}".format(info.get('JSESSIONID'), user[0])
        }
        url = "http://202.203.16.42/syt/zzapply/operation.htm"
        data = {
            'data': '{"xmqkb":{"id":"' + now_time + '"},"c1":"小于37.3℃","c2":"否","type":"XSFXTWJC"}',
            'msgUrl': 'syt/zzapply/list.htm?type=XSFXTWJC&xmid={}'.format(now_time),
            'uploadFileStr': '{}',
            'multiSelectData': '{}',
            'type': 'XSFXTWJC'
        }
        response = requests.post(url, data=data, headers=headers).text
        log.info_log(user[0] + "已经发送打卡信息，状态：" + response)
        if response == 'success':
            log.info_log(user[0] + 'state:OK')
        elif response == 'Applied today':
            raise TaskOverError(user[0] + 'package has been sent')
        elif response == 'error':
            raise ResponseError(user[0] + 'an error has occurred')
        else:
            raise UnknownError(user[0] + 'unknown error' + response)

        message = "学号:" + user[0] + "打卡成功!\r\n全面升级技术，支持更多人打卡!\r\n若您的身体健康不佳，请及时更正并上报！\r\n本项目仅方便网络不佳时使用！\r\n---自动化打卡脚本2.0"
        log.mail_send(user[1] + '@qq.com', mainTask.which_time() + "打卡成功通知", message)
        log.info_log(user[0] + "邮件已发送")

    @staticmethod
    def run(users):
        log.info_log("打卡开始")
        with ThreadPoolExecutor(max_workers=3) as executor:
            result_futures = [executor.submit(mainTask.taskRun, user) for user in users]
            for future in concurrent.futures.as_completed(result_futures):
                try:
                    result = future.result()  # 当子线程中异常时，这里会重新抛出
                except TaskOverError as e:
                    # do noting
                    log.info_log(str(e))
                except ResponseError as e:
                    log.error_log(str(e))
                except UnknownError as e:
                    log.error_log(str(e))
                except Exception as e:
                    log.error_log(str(e))
                else:
                    log.info_log(result)


if __name__ == '__main__':
    users = UserTask().users  # 若不使用数据库，注释掉本行即可，记得新建users列表
    mainTask.run(users)
    LogWriter.send_all_error(log)
