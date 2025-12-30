# 读取toml
import tomllib


with open("../../pyproject.toml", "rb") as f:  # 注意需要以二进制模式打开
    data = tomllib.load(f)
print(data['kaoyan-408-qa-robot'])