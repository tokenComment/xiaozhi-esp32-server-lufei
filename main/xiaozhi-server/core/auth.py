# 从自定义配置模块中导入设置日志的函数，用于配置日志记录
from config.logger import setup_logging

# 获取当前模块的名称作为标签，用于在日志记录中标识来源
TAG = __name__
# 调用设置日志的函数，获取日志记录器
logger = setup_logging()


class AuthenticationError(Exception):
    """
    自定义异常类，用于表示认证过程中出现的异常。
    当认证失败时，抛出此异常以提供明确的错误信息。
    """
    pass


class AuthMiddleware:
    def __init__(self, config):
        """
        初始化认证中间件类。

        :param config: 配置字典，包含服务器的认证相关配置信息。
        """
        # 保存传入的配置信息
        self.config = config
        # 从配置中提取服务器的认证配置，若不存在则使用空字典
        self.auth_config = config["server"].get("auth", {})
        # 构建token查找表，将每个token映射到对应的设备名称
        self.tokens = {
            item["token"]: item["name"]
            for item in self.auth_config.get("tokens", [])
        }
        # 设备白名单，将允许的设备ID存储在集合中，方便快速查找
        self.allowed_devices = set(
            self.auth_config.get("allowed_devices", [])
        )

    async def authenticate(self, headers):
        """
        验证连接请求的认证信息。

        :param headers: 连接请求的头部信息，包含设备ID和认证token等。
        :return: 如果认证成功，返回True；否则抛出AuthenticationError异常。
        """
        # 检查是否启用认证
        if not self.auth_config.get("enabled", False):
            # 若未启用认证，直接返回认证成功
            return True

        # 从头部信息中获取设备ID
        device_id = headers.get("device-id", "")
        # 检查设备是否在白名单中
        if self.allowed_devices and device_id in self.allowed_devices:
            # 若设备在白名单中，返回认证成功
            return True

        # 从头部信息中获取认证头部信息
        auth_header = headers.get("authorization", "")
        # 检查认证头部信息是否以 "Bearer " 开头
        if not auth_header.startswith("Bearer "):
            # 若不符合格式，记录错误日志并抛出认证异常
            logger.bind(tag=TAG).error("Missing or invalid Authorization header")
            raise AuthenticationError("Missing or invalid Authorization header")

        # 提取认证token
        token = auth_header.split(" ")[1]
        # 检查token是否在token查找表中
        if token not in self.tokens:
            # 若token无效，记录错误日志并抛出认证异常
            logger.bind(tag=TAG).error(f"Invalid token: {token}")
            raise AuthenticationError("Invalid token")

        # 若认证成功，记录成功日志
        logger.bind(tag=TAG).info(f"Authentication successful - Device: {device_id}, Token: {self.tokens[token]}")
        return True

    def get_token_name(self, token):
        """
        根据token获取对应的设备名称。

        :param token: 认证token。
        :return: 若token存在，返回对应的设备名称；否则返回None。
        """
        return self.tokens.get(token)