from pydantic import Extra, BaseModel
from typing import Optional, Set


class Config(BaseModel, extra=Extra.ignore):
    openai_api_key: Optional[str] = ""
    openai_model_name: Optional[str] = "gpt-3.5-turbo"
    openai_max_history_limit: Optional[int] = 5
    openai_http_proxy: Optional[str] = None
    enable_private_chat: bool = True
    chatgpt_turbo_public: bool = False  # 群聊是否开启公共会话，即群内共享一个会话
    openai_api_base: Optional[str] = ""     # api转发地址，即国内中转地址
    img_black_list: Optional[Set[str]] = set()   # 禁止某些用户使用图像生成功能


class ConfigError(Exception):
    pass
