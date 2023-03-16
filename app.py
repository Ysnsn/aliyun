"""
    @Author: ImYrS Yang
    @Date: 2023/2/10
    @Copyright: ImYrS Yang
    @Description:
"""

import logging
from os import environ
from sys import argv
from typing import NoReturn, Optional
import json

from configobj import ConfigObj
import requests

from modules import dingtalk, serverchan, pushdeer, telegram, pushplus, smtp
import github


class SignIn:
    """
    签到
    """

    def __init__(
            self,
            config: ConfigObj | dict,
            refresh_token: str,
    ):
        """
        初始化

        :param config: 配置文件, ConfigObj 对象或字典
        :param refresh_token: refresh_token
        """
        self.config = config
        self.refresh_token = refresh_token
        self.hide_refresh_token = self.__hide_refresh_token()
        self.access_token = None
        self.new_refresh_token = None
        self.phone = None
        self.signin_count = 0
        self.signin_reward = None
        self.error = None

    def __hide_refresh_token(self) -> str:
        """
        隐藏 refresh_token

        :return: 隐藏后的 refresh_token
        """
        try:
            return self.refresh_token[:4] + '*' * len(self.refresh_token[4:-4]) + self.refresh_token[-4:]
        except IndexError:
            return self.refresh_token

    def __get_access_token(self) -> bool:
        """
        获取 access_token

        :return: 是否成功
        """
        data = requests.post(
            'https://auth.aliyundrive.com/v2/account/token',
            json={
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
            }
        ).json()

        try:
            if data['code'] in [
                'RefreshTokenExpired', 'InvalidParameter.RefreshToken',
            ]:
                logging.error(f'[{self.hide_refresh_token}] 获取 access token 失败, 可能是 refresh token 无效.')
                self.error = data
                return False
        except KeyError:
            pass

        self.access_token = data['access_token']
        self.new_refresh_token = data['refresh_token']
        self.phone = data['user_name']

        return True

    def __sign_in(self) -> NoReturn:
        """
        签到函数

        :return:
        """
        data = requests.post(
            'https://member.aliyundrive.com/v1/activity/sign_in_list',
            headers={
                'Authorization': f'Bearer {self.access_token}',
            },
            json={},
        ).json()

        if 'success' not in data:
            logging.error(f'[{self.phone}] 签到失败, 错误信息: {data}')
            self.error = data
            return

        current_day = None
        for i, day in enumerate(data['result']['signInLogs']):
            if day['status'] == 'miss':
                current_day = data['result']['signInLogs'][i - 1]
                break

        reward = (
            '无奖励'
            if not current_day['isReward']
            else f'获得 {current_day["reward"]["name"]} {current_day["reward"]["description"]}'
        )

        self.signin_count = data['result']['signInCount']
        self.signin_reward = reward

        logging.info(f'[{self.phone}] 签到成功, 本月累计签到 {self.signin_count} 天.')
        logging.info(f'[{self.phone}] 本次签到{reward}')

    def __generate_result(self) -> dict:
        """
        获取签到结果

        :return: 签到结果
        """
        user = self.phone or self.hide_refresh_token
        text = (
            f'[{user}] 签到成功, 本月累计签到 {self.signin_count} 天.\n本次签到{self.signin_reward}'
            if self.signin_count
            else f'[{user}] 签到失败\n{json.dumps(self.error, indent=2, ensure_ascii=False)}'
        )

        text_html = (
            f'<code>{user}</code> 签到成功, 本月累计签到 {self.signin_count} 天.\n本次签到{self.signin_reward}'
            if self.signin_count
            else (
                f'<code>{user}</code> 签到失败\n'
                f'<code>{json.dumps(self.error, indent=2, ensure_ascii=False)}</code>'
            )
        )

        return {
            'success': True if self.signin_count else False,
            'user': self.phone or self.hide_refresh_token,
            'refresh_token': self.new_refresh_token or self.refresh_token,
            'count': self.signin_count,
            'reward': self.signin_reward,
            'text': text,
            'text_html': text_html,
        }

    def run(self) -> dict:
        """
        运行签到

        :return: 签到结果
        """
        result = self.__get_access_token()

        if result:
            self.__sign_in()

        return self.__generate_result()


def push(
        config: ConfigObj | dict,
        content: str,
        content_html: str,
        title: Optional[str] = None,
) -> NoReturn:
    """
    推送签到结果

    :param config: 配置文件, ConfigObj 对象或字典
    :param content: 推送内容
    :param content_html: 推送内容, HTML 格式
    :param title: 推送标题

    :return:
    """
    configured_push_types = [
        i.lower().strip()
        for i in (
            [config['push_types']]
            if type(config['push_types']) == str
            else config['push_types']
        )
    ]

    for push_type, pusher in {
        'dingtalk': dingtalk,
        'serverchan': serverchan,
        'pushdeer': pushdeer,
        'telegram': telegram,
        'pushplus': pushplus,
        'smtp': smtp,
    }.items():
        if push_type in configured_push_types:
            pusher.push(config, content, content_html, title)


def init_logger() -> NoReturn:
    """
    初始化日志系统

    :return:
    """
    log = logging.getLogger()
    log.setLevel(logging.INFO)
    log_format = logging.Formatter(
        '%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s: %(message)s'
    )

    # Console
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(log_format)
    log.addHandler(ch)

    # Log file
    log_name = 'aliyun_auto_signin.log'
    fh = logging.FileHandler(log_name, mode='a', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(log_format)
    log.addHandler(fh)


def get_config_from_env() -> Optional[dict]:
    """
    从环境变量获取配置

    :return: 配置字典, 配置缺失返回 None
    """
    try:
        return {
            'refresh_tokens': (
                [environ['REFRESH_TOKENS']]
                if not environ['REFRESH_TOKENS']
                else environ['REFRESH_TOKENS'].split(',')
            ),
            'push_types': (
                [environ['PUSH_TYPES']]
                if not environ['PUSH_TYPES']
                else environ['PUSH_TYPES'].split(',')
            ),
            'serverchan_send_key': environ['SERVERCHAN_SEND_KEY'],
            'telegram_endpoint': 'https://api.telegram.org',
            'telegram_bot_token': environ['TELEGRAM_BOT_TOKEN'],
            'telegram_chat_id': environ['TELEGRAM_CHAT_ID'],
            'telegram_proxy': None,
            'pushplus_token': environ['PUSHPLUS_TOKEN'],
            'smtp_host': environ['SMTP_HOST'],
            'smtp_port': environ['SMTP_PORT'],
            'smtp_tls': environ['SMTP_TLS'],
            'smtp_user': environ['SMTP_USER'],
            'smtp_password': environ['SMTP_PASSWORD'],
            'smtp_sender': environ['SMTP_SENDER'],
            'smtp_receiver': environ['SMTP_RECEIVER'],
        }
    except KeyError as e:
        logging.error(f'环境变量 {e} 缺失.')
        return None


def main():
    """
    主函数

    :return:
    """
    environ['NO_PROXY'] = '*'  # 禁止代理

    init_logger()  # 初始化日志系统

    by_action = (
        True
        if len(argv) == 2 and argv[1] == 'action'
        else False
    )

    # 获取配置
    config = (
        get_config_from_env()
        if by_action
        else ConfigObj('config.ini', encoding='UTF8')
    )

    if not config:
        logging.error('获取配置失败.')
        return

    # 获取所有 refresh token 指向用户
    users = (
        [config['refresh_tokens']]
        if type(config['refresh_tokens']) == str
        else config['refresh_tokens']
    )

    results = []

    for user in users:
        result = SignIn(config=config, refresh_token=user).run()
        results.append(result)

    # 合并推送
    text = '\n\n'.join([i['text'] for i in results])
    text_html = '\n\n'.join([i['text_html'] for i in results])

    push(config, text, text_html, '阿里云盘签到')

    # 更新 refresh token
    new_users = [i['refresh_token'] for i in results]

    if not by_action:
        config['refresh_tokens'] = ','.join(new_users)
    else:
        try:
            github.update_secret('REFRESH_TOKENS', ','.join(new_users))
        except Exception as e:
            err = f'Action 更新 Github Secrets 失败: {e}'
            logging.error(err)
            push(config, err, err, '阿里云盘签到')


if __name__ == '__main__':
    main()
