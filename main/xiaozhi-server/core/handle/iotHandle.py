import json
from config.logger import setup_logging

TAG = __name__  # 定义日志标签，用于在日志中标识模块名称
logger = setup_logging()  # 初始化日志记录器，用于记录程序运行过程中的日志信息


class IotDescriptor:
    """
    用于表示物联网设备的描述类。
    
    Attributes:
    ----------
    name : str
        物联网设备的名称。
    description : str
        设备的简要描述。
    properties : list
        包含设备属性的列表，每个属性是一个字典。
    methods : list
        包含设备方法的列表，每个方法是一个字典。
    """

    def __init__(self, name, description, properties, methods):
        """
        初始化物联网设备描述。
        
        参数:
            name (str): 设备名称。
            description (str): 设备描述。
            properties (dict): 设备属性的字典。
            methods (dict): 设备方法的字典。
        """
        self.name = name
        self.description = description
        self.properties = []  # 初始化属性列表
        self.methods = []  # 初始化方法列表

        # 根据描述创建属性
        for key, value in properties.items():
            property_item = globals()[key] = {}  # 创建一个空字典，名字是属性名
            property_item['name'] = key
            property_item["description"] = value["description"]
            if value["type"] == "number":
                property_item["value"] = 0  # 数值类型属性默认值为0
            elif value["type"] == "boolean":
                property_item["value"] = False  # 布尔类型属性默认值为False
            else:
                property_item["value"] = ""  # 其他类型属性默认值为空字符串
            self.properties.append(property_item)  # 将属性添加到列表中

        # 根据描述创建方法
        for key, value in methods.items():
            method = globals()[key] = {}  # 创建一个空字典，名字是方法名
            method["description"] = value["description"]
            method['name'] = key
            for k, v in value["parameters"].items():
                method[k] = {}  # 创建方法参数
                method[k]["description"] = v["description"]
                if v["type"] == "number":
                    method[k]["value"] = 0  # 数值类型参数默认值为0
                elif v["type"] == "boolean":
                    method[k]["value"] = False  # 布尔类型参数默认值为False
                else:
                    method[k]["value"] = ""  # 其他类型参数默认值为空字符串
            self.methods.append(method)  # 将方法添加到列表中


async def handleIotDescriptors(conn, descriptors):
    """
    处理物联网设备描述。
    
    参数:
        conn: 客户端连接对象，包含设备描述信息。
        descriptors (list): 设备描述列表，每个描述是一个字典。
        
    示例:
        descriptors = [{
            "name": "Speaker",
            "description": "当前 AI 机器人的扬声器",
            "properties": {
                "volume": {"description": "当前音量值", "type": "number"}
            },
            "methods": {
                "SetVolume": {
                    "description": "设置音量",
                    "parameters": {"volume": {"description": "0到100之间的整数", "type": "number"}}
                }
            }
        }]
    """
    for descriptor in descriptors:
        # 创建物联网设备描述对象
        iot_descriptor = IotDescriptor(
            descriptor["name"],
            descriptor["description"],
            descriptor["properties"],
            descriptor["methods"]
        )
        conn.iot_descriptors[descriptor["name"]] = iot_descriptor  # 将设备描述存储到连接对象中

    # 设置默认音量（从配置文件中获取或使用默认值）
    default_iot_volume = 100
    if "iot" in conn.config:
        default_iot_volume = conn.config["iot"]["Speaker"]["volume"]
    logger.bind(tag=TAG).info(f"服务端设置音量为 {default_iot_volume}")
    await send_iot_conn(conn, "Speaker", "SetVolume", {"volume": default_iot_volume})  # 发送音量设置指令


async def handleIotStatus(conn, states):
    """
    处理物联网设备状态。
    
    参数:
        conn: 客户端连接对象，包含设备状态信息。
        states (list): 设备状态列表，每个状态是一个字典。
        
    示例:
        states = [{
            "name": "Speaker",
            "state": {"volume": 100}
        }]
    """
    for state in states:
        for key, value in conn.iot_descriptors.items():
            if key == state["name"]:  # 找到对应的设备
                for property_item in value.properties:
                    for k, v in state["state"].items():
                        if property_item["name"] == k:  # 找到对应的属性
                            if type(v) != type(property_item["value"]):
                                logger.bind(tag=TAG).error(f"属性 {property_item['name']} 的值类型不匹配")
                                break
                            else:
                                property_item["value"] = v  # 更新属性值
                                logger.bind(tag=TAG).info(f"物联网状态更新: {key} , {property_item['name']} = {v}")
                            break
                break


async def get_iot_status(conn, name, property_name):
    """
    获取物联网设备的属性状态。
    
    参数:
        conn: 客户端连接对象，包含设备状态信息。
        name (str): 设备名称。
        property_name (str): 属性名称。
        
    返回:
        属性值，类型为 int、bool 或 str。
    """
    for key, value in conn.iot_descriptors.items():
        if key == name:  # 找到对应的设备
            for property_item in value.properties:
                if property_item["name"] == property_name:  # 找到对应的属性
                    return property_item["value"]
    return None


async def send_iot_conn(conn, name, method_name, parameters):
    """
    发送物联网设备指令。
    
    参数:
        conn: 客户端连接对象，包含 WebSocket 连接。
        name (str): 设备名称。
        method_name (str): 方法名称。
        parameters (dict): 方法参数。
        
    发送示例:
        {
            "type": "iot",
            "commands": [
                {
                    "name": "Speaker",
                    "method": "SetVolume",
                    "parameters": {"volume": 100}
                }
            ]
        }
    """
    for key, value in conn.iot_descriptors.items():
        if key == name:  # 找到对应的设备
            for method in value.methods:
                if method["name"] == method_name:  # 找到对应的方法
                    await conn.websocket.send(json.dumps({
                        "type": "iot",
                        "commands": [
                            {
                                "name": name,
                                "method": method_name,
                                "parameters": parameters
                            }
                        ]
                    }))
                    return
    logger.bind(tag=TAG).error(f"未找到方法 {method_name}")