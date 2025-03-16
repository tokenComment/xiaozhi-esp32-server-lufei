import requests
from config.logger import setup_logging
 
 
# 定义一个名为 HassHandler 的类，用于处理与 Home Assistant 相关的操作
class HassHandler:
    # 类的初始化方法，当创建 HassHandler 类的实例时会调用该方法
    def __init__(self, config):
        """
        初始化 HassHandler 类的实例。

        :param config: 包含配置信息的字典，其中应包含 LLM 相关配置，
                       且 LLM 配置中包含 HomeAssistant 相关配置，
                       HomeAssistant 配置包含 base_url 和 api_key。
        """
        # 将传入的配置信息保存到实例的 config 属性中
        self.config = config
        # 从配置信息中提取 Home Assistant 的基础 URL，并保存到实例的 base_url 属性中
        self.base_url = config["LLM"]['HomeAssistant']['base_url']
        # 从配置信息中提取 Home Assistant 的 API 密钥，并保存到实例的 api_key 属性中
        self.api_key = config["LLM"]['HomeAssistant']['api_key']

    # 定义一个异步方法，用于切换 Home Assistant 中设备的状态
    async def hass_toggle_device(self, conn, entity_id, state):
        """
        切换 Home Assistant 中设备的状态。

        :param conn: 连接对象，此方法中未使用该参数，但可能在其他逻辑中有作用。
        :param entity_id: 要操作的设备的实体 ID，格式为 domain.entity_name。
        :param state: 要将设备切换到的状态，取值为 "on" 或 "off"。
        :return: 操作结果的描述信息，若成功则返回操作成功信息，若失败则返回错误信息。
        """
        # 将实体 ID 按 "." 分割成多个部分，存储在 domains 列表中
        domains = entity_id.split(".")
        # 检查分割后的列表长度是否大于 1
        if len(domains) > 1:
            # 如果长度大于 1，将列表的第一个元素作为设备的域（domain）
            domain = domains[0]
        else:
            # 如果长度不大于 1，说明实体 ID 格式错误，返回执行失败信息
            return "执行失败，错误的设备id"

        # 检查要切换的状态是否为 "on"
        if state == "on":
            # 如果是 "on"，设置描述信息为 "打开"
            description = "打开"
            # 检查设备的域是否为 "cover"（可能是遮阳帘等设备）
            if domain == 'cover':
                # 如果是 "cover"，设置要执行的操作动作为 "open_cover"
                action = "open_cover"
            # 检查设备的域是否为 "vacuum"（可能是扫地机器人等设备）
            elif domain == 'vacuum':
                # 如果是 "vacuum"，设置要执行的操作动作为 "start"
                action = "start"
            else:
                # 对于其他类型的设备，设置要执行的操作动作为 "turn_on"
                action = "turn_on"
        # 检查要切换的状态是否为 "off"
        elif state == "off":
            # 如果是 "off"，设置描述信息为 "关闭"
            description = "关闭"
            # 检查设备的域是否为 "cover"
            if domain == 'cover':
                # 如果是 "cover"，设置要执行的操作动作为 "close_cover"
                action = "close_cover"
            # 检查设备的域是否为 "vacuum"
            elif domain == 'vacuum':
                # 如果是 "vacuum"，设置要执行的操作动作为 "stop"
                action = "stop"
            else:
                # 对于其他类型的设备，设置要执行的操作动作为 "turn_off"
                action = "turn_off"
        else:
            # 如果状态既不是 "on" 也不是 "off"，返回未知操作的错误信息
            return "执行失败，未知的action"

        # 构建要发送请求的 URL，包含基础 URL 和操作的域及动作
        url = f"{self.base_url}/api/services/{domain}/{action}"
        # 构建请求头，包含授权信息和内容类型
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        # 构建请求的数据，包含要操作的设备的实体 ID
        data = {
            "entity_id": entity_id
        }

        # 发送 POST 请求到构建好的 URL，携带请求头和数据
        response = requests.post(url, headers=headers, json=data)
        # 检查响应的状态码是否为 200（表示请求成功）
        if response.status_code == 200:
            # 如果成功，返回设备状态切换成功的描述信息
            return f"设备已{description}"
        else:
            # 如果失败，返回设备状态切换失败及错误码的信息
            return f"切换失败，错误码: {response.status_code}"

    # 定义一个异步方法，用于在 Home Assistant 中播放音乐
    async def hass_play_music(self, conn, entity_id, media_content_id):
        """
        在 Home Assistant 中播放指定的音乐。

        :param conn: 连接对象，此方法中未使用该参数，但可能在其他逻辑中有作用。
        :param entity_id: 要播放音乐的设备的实体 ID。
        :param media_content_id: 要播放的音乐的内容 ID。
        :return: 操作结果的描述信息，若成功则返回播放信息，若失败则返回错误信息。
        """
        # 构建要发送请求的 URL，用于播放音乐的服务接口
        url = f"{self.base_url}/api/services/music_assistant/play_media"
        # 构建请求头，包含授权信息和内容类型
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        # 构建请求的数据，包含要播放音乐的设备的实体 ID 和音乐内容 ID
        data = {
            "entity_id": entity_id,
            "media_id": media_content_id
        }
        # 发送 POST 请求到构建好的 URL，携带请求头和数据
        response = requests.post(url, headers=headers, json=data)
        # 检查响应的状态码是否为 200（表示请求成功）
        if response.status_code == 200:
            # 如果成功，返回正在播放音乐的描述信息
            return f"正在播放{media_content_id}的音乐"
        else:
            # 如果失败，返回音乐播放失败及错误码的信息
            return f"音乐播放失败，错误码: {response.status_code}"