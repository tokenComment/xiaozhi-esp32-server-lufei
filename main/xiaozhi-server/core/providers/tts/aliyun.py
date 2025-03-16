import os
import uuid
import json
import hmac
import hashlib
import base64
import requests
from datetime import datetime
from core.providers.tts.base import TTSProviderBase

import http.client
import urllib.parse
import time
import uuid
from urllib import parse

# 访问令牌生成类
class AccessToken:
    # 对文本进行URL编码，确保特殊字符被正确处理
    @staticmethod
    def _encode_text(text):
        encoded_text = parse.quote_plus(text)
        return encoded_text.replace('+', '%20').replace('*', '%2A').replace('%7E', '~')
    
    # 对字典进行排序并URL编码
    @staticmethod
    def _encode_dict(dic):
        keys = dic.keys()
        dic_sorted = [(key, dic[key]) for key in sorted(keys)]  # 按照键排序
        encoded_text = parse.urlencode(dic_sorted)  # URL编码
        return encoded_text.replace('+', '%20').replace('*', '%2A').replace('%7E', '~')
    
    # 生成阿里云TTS的临时访问令牌
    @staticmethod
    def create_token(access_key_id, access_key_secret):
        # 定义请求参数
        parameters = {
            'AccessKeyId': access_key_id,
            'Action': 'CreateToken',
            'Format': 'JSON',
            'RegionId': 'cn-shanghai',
            'SignatureMethod': 'HMAC-SHA1',
            'SignatureNonce': str(uuid.uuid1()),  # 唯一随机数
            'SignatureVersion': '1.0',
            'Timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),  # 生成时间戳
            'Version': '2019-02-28'
        }
        
        # 构造规范化的请求字符串
        query_string = AccessToken._encode_dict(parameters)
        print('规范化的请求字符串: %s' % query_string)
        
        # 构造待签名字符串
        string_to_sign = 'GET' + '&' + AccessToken._encode_text('/') + '&' + AccessToken._encode_text(query_string)
        print('待签名的字符串: %s' % string_to_sign)
        
        # 计算HMAC-SHA1签名
        secreted_string = hmac.new(
            bytes(access_key_secret + '&', encoding='utf-8'),
            bytes(string_to_sign, encoding='utf-8'),
            hashlib.sha1
        ).digest()
        
        # Base64编码签名
        signature = base64.b64encode(secreted_string)
        print('签名: %s' % signature)
        
        # 进行URL编码
        signature = AccessToken._encode_text(signature)
        print('URL编码后的签名: %s' % signature)
        
        # 生成完整的请求URL
        full_url = f'http://nls-meta.cn-shanghai.aliyuncs.com/?Signature={signature}&{query_string}'
        print('url: %s' % full_url)
        
        # 发送HTTP GET请求获取Token
        response = requests.get(full_url)
        if response.ok:
            root_obj = response.json()
            key = 'Token'
            if key in root_obj:
                token = root_obj[key]['Id']
                expire_time = root_obj[key]['ExpireTime']
                return token, expire_time  # 返回Token及其过期时间
        
        print(response.text)
        return None, None  # 获取失败返回None


# 语音合成提供者类，继承TTSProviderBase
class TTSProvider(TTSProviderBase):

    # 初始化语音合成提供者
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        
        # 获取配置中的Access Key ID和Secret
        access_key_id = config.get("access_key_id")
        access_key_secret = config.get("access_key_secret")
        
        if access_key_id and access_key_secret:
            # 如果提供了密钥，则生成临时Token
            token, expire_time = AccessToken.create_token(access_key_id, access_key_secret)
        else:
            # 否则直接使用长期Token
            token = config.get("token")
            expire_time = None
        
        print('token: %s, expire time(s): %s' % (token, expire_time))

        # 配置参数
        self.appkey = config.get("appkey")  # 语音合成应用的AppKey
        self.token = token  # 访问令牌
        self.format = config.get("format", "wav")  # 语音输出格式（默认为WAV）
        self.sample_rate = config.get("sample_rate", 16000)  # 采样率（默认为16kHz）
        self.voice = config.get("voice", "xiaoyun")  # 语音合成的发音人（默认为xiaoyun）
        self.volume = config.get("volume", 50)  # 音量大小（默认50）
        self.speech_rate = config.get("speech_rate", 0)  # 语速（默认0）
        self.pitch_rate = config.get("pitch_rate", 0)  # 音调（默认0）

        # 配置API访问的服务器地址
        self.host = config.get("host", "nls-gateway-cn-shanghai.aliyuncs.com")
        self.api_url = f"https://{self.host}/stream/v1/tts"
        
        # 设置请求头
        self.header = {
            "Content-Type": "application/json"
        }

    # 生成带时间戳和UUID的文件名
    def generate_filename(self, extension=".wav"):
        return os.path.join(
            self.output_file,
            f"tts-{__name__}{datetime.now().date()}@{uuid.uuid4().hex}{extension}"
        )

    # 异步文本转语音方法
    async def text_to_speak(self, text, output_file):
        # 构造TTS请求参数
        request_json = {
            "appkey": self.appkey,
            "token": self.token,
            "text": text,
            "format": self.format,
            "sample_rate": self.sample_rate,
            "voice": self.voice,
            "volume": self.volume,
            "speech_rate": self.speech_rate,
            "pitch_rate": self.pitch_rate
        }

        print(self.api_url, json.dumps(request_json, ensure_ascii=False))
        
        try:
            # 发送POST请求进行语音合成
            resp = requests.post(self.api_url, json.dumps(request_json), headers=self.header)
            
            # 检查响应的Content-Type是否为音频格式
            if resp.headers['Content-Type'].startswith('audio/'):
                with open(output_file, 'wb') as f:
                    f.write(resp.content)  # 保存音频文件
                return output_file  # 返回保存的音频文件路径
            else:
                # 如果返回的不是音频数据，则抛出异常
                raise Exception(f"{__name__} status_code: {resp.status_code} response: {resp.content}")
        except Exception as e:
            # 捕获异常并抛出
            raise Exception(f"{__name__} error: {e}")
