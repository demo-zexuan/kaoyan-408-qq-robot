import nonebot
from nonebot.adapters.onebot.v11 import Adapter

def main():
    # 1. 初始化 NoneBot（指定环境文件和配置文件，建议使用绝对路径避免路径问题）
    nonebot.init(_env_file='../.env')
    nonebot.load_from_toml("../pyproject.toml")

    # 2. 注册适配器（确保 driver 初始化完成后再注册）
    driver = nonebot.get_driver()
    driver.register_adapter(Adapter)

    # 3. 加载插件（调整顺序，先加载内置插件，再加载自定义插件）
    nonebot.load_builtin_plugin("echo")
    nonebot.load_plugin('nonebot_plugin_status')
    nonebot.load_plugins("./plugins")

    # 4. 运行 NoneBot（指定端口，避免端口冲突，可选）
    nonebot.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    main()