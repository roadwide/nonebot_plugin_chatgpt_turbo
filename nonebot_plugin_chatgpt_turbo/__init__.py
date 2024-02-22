import nonebot
import openai
import argparse

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
from typing import Union

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

# 不带上下文的聊天
chat_request = on_command("gpt4", block=False, priority=1)

# 清除历史记录
clear_request = on_command("clear", block=True, priority=1)

# 绘画
draw = on_command("draw")

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


@draw.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    if (event.user_id in plugin_config.img_black_list):
        await draw.finish("您在黑名单中，请虔诚忏悔解封！")
    cmd_text = arg.extract_plain_text().strip()
    await draw.send(MessageSegment.text("正在获取创作灵感......".format(cmd_text)))

    try:
        openai.api_key = api_key
        response = openai.Image.create(
            model="dall-e-2",
            prompt=cmd_text,
            size="256x256",
            quality="standard",
            n=1,
        )

        img_url = response.data[0].url
        file_id = await bot.upload_file(type="url",
                                        name="test.png",
                                        url=img_url
                                        )
        message = MessageSegment.image(file_id=file_id["file_id"])
        await draw.send(message)
    except Exception as e:
        await draw.finish(f"An error occurred: {e}")


@chat_request.handle()
async def _(event: MessageEvent, msg: Message = CommandArg()):

    if isinstance(event, PrivateMessageEvent) and not plugin_config.enable_private_chat:
        chat_record.finish("对不起，私聊暂不支持此功能。")

    content = msg.extract_plain_text()
    if content == "" or content is None:
        await chat_request.finish(MessageSegment.text("内容不能为空！"))

    await chat_request.send(MessageSegment.text("ChatGPT正在思考中......"))

    try:
        res = await get_response(content, proxy)

    except Exception as error:
        await chat_request.finish(str(error))
    await chat_request.finish(MessageSegment.text(res))

# 根据消息类型创建会话id
def create_session_id(event):
    if isinstance(event, PrivateMessageEvent):
        session_id = f"Private_{event.user_id}"
    elif public:
        session_id = event.get_session_id().replace(f"{event.user_id}", "Public")
    else:
        session_id = event.get_session_id()
    return session_id

# 单条对话请求, gpt4
async def get_response(content, proxy):
    openai.api_key = api_key
    if proxy != "":
        openai.proxy = proxy

    res_ = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "user", "content": content}
        ]
    )

    res = res_.choices[0].message.content

    while res.startswith("\n") != res.startswith("？"):
        res = res[1:]

    return res


# 调试命令
help = on_command("help")
get_group_list = on_command("get_group_list")
get_group_member_list = on_command("get_group_member_list")
send_link = on_command("send_link")
send_message = on_command("send_message")

@help.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    help_dic = {
        "/get_group_list": "获取群组列表",
        "/get_group_member_list [group_id]": "获取群组成员",
        "/send_message --type --id --content ": "发送消息",
        "/send_link --type --id --title --des --url --img_url": "发送链接" 
    }
    message = ''
    for k, v in help_dic.items():
        message += k + v + '\n'
    await help.finish(message)


@get_group_list.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    cmd_text = arg.extract_plain_text().strip()
    group_list = await bot.get_group_list()
    await get_group_list.finish(str(group_list))


@get_group_member_list.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    cmd_text = arg.extract_plain_text().strip()
    group_member_list = await bot.get_group_member_list(group_id=cmd_text)
    await get_group_member_list.finish(str(group_member_list))


@send_message.handle()
async def _(bot: Bot, cmd_arg: Message = CommandArg()):
    # 使用 argparse 解析命令参数
    parser = argparse.ArgumentParser(prog='send_link')
    parser.add_argument('--type', type=str, help='消息类型 group/private')
    parser.add_argument('--id', type=str, help='user_id/group_id')
    parser.add_argument('--content', type=str, help='消息内容')
    try:
        args = parser.parse_args(cmd_arg.extract_plain_text().strip().split(' '))
        message = MessageSegment.text(unescape(args.content))
        await bot.send_message(detail_type=args.type,
                            user_id=args.id,
                            group_id=args.id,
                            message=message) 
    except:
        await send_message.finish("发送失败")
    await send_message.finish("发送成功")


@send_link.handle()
async def _(bot: Bot, cmd_arg: Message = CommandArg()):
    # 使用 argparse 解析命令参数
    parser = argparse.ArgumentParser(prog='send_link')
    parser.add_argument('--type', type=str, help='消息类型 group/private')
    parser.add_argument('--id', type=str, help='user_id/group_id')
    parser.add_argument('--title', type=str, help='文章标题')
    parser.add_argument('--des', type=str, help='消息卡片摘要')
    parser.add_argument('--url', type=str, help='文章链接')
    parser.add_argument('--img_url', type=str, help='消息图片url', default=None)
    try:
        args = parser.parse_args(cmd_arg.extract_plain_text().strip().split(' '))
        file_id = {"file_id": None}
        if args.img_url:
            file_id = await bot.upload_file(type="url",
                                        name="test.png",
                                        url=args.img_url
                                        )
        message = MessageSegment("wx.link",{
            "title": args.title,
            "des": args.des,
            "url": args.url,
            "file_id": file_id["file_id"]
            })
        await bot.send_message(detail_type=args.type,
                            user_id=args.id,
                            group_id=args.id,
                            message=message) 
    except:
        await send_link.finish("发送失败")
    await send_link.finish("发送成功")