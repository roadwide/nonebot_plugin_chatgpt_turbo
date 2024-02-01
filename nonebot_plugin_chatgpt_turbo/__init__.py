import nonebot
import openai

from html import unescape
from nonebot import on_command, on_message, get_bot
from nonebot.params import CommandArg
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v12 import (
    Bot,
    Message, 
    MessageSegment,
    GroupMessageEvent, 
    PrivateMessageEvent, 
    MessageEvent)
from .config import Config, ConfigError
from .ChatSession import ChatSession

# 配置导入
plugin_config = Config.parse_obj(nonebot.get_driver().config.dict())

if plugin_config.openai_api_base:
    openai.api_base = plugin_config.openai_api_base

if plugin_config.openai_http_proxy:
    proxy = {'http': plugin_config.openai_http_proxy, 'https': plugin_config.openai_http_proxy}
else:
    proxy = ""

if not plugin_config.openai_api_key:
    raise ConfigError("请设置 openai_api_key")

api_key = plugin_config.openai_api_key
model_id = plugin_config.openai_model_name
max_limit = plugin_config.openai_max_history_limit
public = plugin_config.chatgpt_turbo_public
session = {}

# on_message的判断规则。群消息需要艾特，私聊直接回复
async def rule_check(event: MessageEvent, bot: Bot) -> bool:
    # 群聊
    if isinstance(event, GroupMessageEvent):
        if event.is_tome():
            return True
        else:
            return False
    # 私聊
    elif isinstance(event, PrivateMessageEvent):
        if plugin_config.enable_private_chat:
            return True
        else:
            return False
    return False

# 带上下文的聊天
chat_record = on_message(rule=rule_check)

# 清除历史记录
clear_request = on_command("clear", block=True, priority=1)


# 带记忆的聊天
@chat_record.handle()
async def _(event: MessageEvent):
    #屏蔽 / 开头的消息，防止其他插件命令触发机器人
    if event.get_message().extract_plain_text().startswith('/'):
        return

    # 检测是否填写 API key
    if api_key == "":
        await chat_record.finish(MessageSegment.text("请先配置openai_api_key"), at_sender=True)

    # 提取提问内容
    content = unescape(event.get_plaintext().strip())
    if content == "" or content is None:
        await chat_record.finish(MessageSegment.text("内容不能为空！"), at_sender=True)

    await chat_record.send(MessageSegment.text("ChatGPT正在思考中......"))

    # 创建会话ID
    session_id = create_session_id(event)

    # 初始化保存空间
    if session_id not in session:
        session[session_id] = ChatSession(api_key=api_key, model_id=model_id, max_limit=max_limit)

    # 开始请求
    try:
        res = await session[session_id].get_response(content, proxy)

    except Exception as error:
        await chat_record.finish(str(error), at_sender=True)
    await chat_record.finish(MessageSegment.text(res), at_sender=True)


@clear_request.handle()
async def _(event: MessageEvent):
    bot = get_bot()
    is_superuser = await SUPERUSER(bot, event)
    if not is_superuser:
        await clear_request.finish(MessageSegment.text("只有超级管理员可以使用该命令！"), at_sender=True)
    session_id = create_session_id(event)
    if session_id in session:
        del session[create_session_id(event)]
        await clear_request.finish(MessageSegment.text("成功清除历史记录！"), at_sender=True)
    else:
        await clear_request.finish(MessageSegment.text("不存在历史记录！"), at_sender=True)


# 根据消息类型创建会话id
def create_session_id(event):
    if isinstance(event, PrivateMessageEvent):
        session_id = f"Private_{event.user_id}"
    elif public:
        session_id = event.get_session_id().replace(f"{event.user_id}", "Public")
    else:
        session_id = event.get_session_id()
    return session_id

# 发送请求模块
async def get_response(content, proxy):
    openai.api_key = api_key
    if proxy != "":
        openai.proxy = proxy

    res_ = await openai.ChatCompletion.acreate(
        model=model_id,
        messages=[
            {"role": "user", "content": content}
        ]
    )

    res = res_.choices[0].message.content

    while res.startswith("\n") != res.startswith("？"):
        res = res[1:]

    return res