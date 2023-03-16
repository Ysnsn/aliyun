"""
    @Author: ImYrS Yang
    @Date: 2023/2/13
    @Copyright: ImYrS Yang
    @Description: 
"""

from typing import Optional
import logging

import requests
from configobj import ConfigObj


class Pusher:

    def __init__(
            self,
            endpoint: str,
            token: str,
            chat_id: str,
            proxy: Optional[str] = None
    ):
        self.endpoint = endpoint
        self.token = token
        self.chat_id = chat_id
        self.proxy = proxy

    def send(self, title: str, content: str) -> Optional[dict]:
        """
        发送消息

        :param title: 通知标题
        :param content: 消息内容
        :return:
        """
        resp = requests.post(
            self.endpoint + f'/bot{self.token}/sendMessage',
            json={
                'chat_id': self.chat_id,
                'text': f'<b>{title}</b>\n\n{content}',
                'parse_mode': 'HTML',
            },
            proxies={
                'http': self.proxy,
                'https': self.proxy,
            } if self.proxy else None,
            timeout=10,
        )

        if resp.status_code == 200:
            return resp.json()

        logging.error(f'Telegram 推送失败: {resp.status_code} {resp.text}')
        return None


def push(
        config: ConfigObj | dict,
        content: str,
        content_html: str,
        title: str,
) -> bool:
    """
    签到消息推送

    :param config: 配置文件, ConfigObj 对象 | dict
    :param content: 推送内容
    :param content_html: 推送内容, HTML 格式
    :param title: 标题
    :return:
    """
    if (
            not config['telegram_endpoint']
            or not config['telegram_bot_token']
            or not config['telegram_chat_id']
    ):
        logging.error('Telegram 推送参数配置不完整')
        return False

    try:
        pusher = Pusher(
            config['telegram_endpoint'],
            config['telegram_bot_token'],
            config['telegram_chat_id'],
            config['telegram_proxy'],
        )
        if pusher.send(title, content_html):
            logging.info('Telegram 推送成功')
    except Exception as e:
        logging.error(f'Telegram 推送失败, 错误信息: {e}')
        return False

    return True
