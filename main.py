import os
import json
import re
from typing import Dict, Union, List

from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import At, Plain

@register("astrbot_plugin_ymyz", "Taropoi", "恐怖则批", "1.1.0", "https://github.com/waterladleh/astrbot_plugin_ymyz")
class ZePiPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
        # 1. 修改数据文件路径：直接放在 main.py 同级目录下
        # os.path.dirname(__file__) 获取当前脚本所在目录
        self.data_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_file = os.path.join(self.data_dir, "zepi_list.json")
        
        # 加载数据
        self.data = self._load_data()
        logger.info(f"则批管理插件已加载，数据路径: {self.data_file}")

    def _load_data(self) -> Dict[str, Dict[str, str]]:
        if not os.path.exists(self.data_file):
            return {}
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            
            # 简单的数据迁移逻辑：如果发现旧的 List 结构，转换为 Dict
            new_data = {}
            for gid, content in raw_data.items():
                if isinstance(content, list):
                    # 旧数据迁移，默认昵称为"未知"
                    new_data[gid] = {str(uid): "未知" for uid in content}
                else:
                    new_data[gid] = content
            return new_data

        except Exception as e:
            logger.error(f"加载则批数据失败: {e}")
            return {}

    def _save_data(self):
        """保存数据到文件"""
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存则批数据失败: {e}")

    def _get_at_info(self, event: AstrMessageEvent):
        """
        解析消息，提取 @的对象 和 附带的文本(昵称)
        返回: (qq_int, nickname_str) 或 (None, None)
        """
        message_chain = event.message_obj.message
        target_qq = None
        nickname_parts = []
        
        found_at = False

        for component in message_chain:
            # 1. 识别 At 组件
            is_at = False
            current_qq = None
            
            if isinstance(component, At):
                is_at = True
                current_qq = component.qq
            elif isinstance(component, dict) and component.get("type") == "at":
                is_at = True
                current_qq = component.get("data", {}).get("qq")
            elif hasattr(component, "type") and getattr(component, "type") == "at":
                is_at = True
                current_qq = getattr(component, "qq", None)

            if is_at:
                if current_qq and str(current_qq) != "all":
                    target_qq = int(current_qq)
                    found_at = True
                continue # 继续处理下一个组件

            # 2. 如果已经找到了 At，后续的 Plain 文本即为昵称
            if found_at:
                if isinstance(component, Plain):
                    nickname_parts.append(component.text)
                elif isinstance(component, dict) and component.get("type") == "text":
                    nickname_parts.append(component.get("data", {}).get("text", ""))
                elif hasattr(component, "type") and getattr(component, "type") == "text":
                     nickname_parts.append(getattr(component, "text", ""))

        if target_qq:
            # 拼接后续文本并去除首尾空白
            full_nick = "".join(nickname_parts).strip()
            return target_qq, full_nick
        
        return None, None

    @filter.command("你是则批")
    async def add_zepi(self, event: AstrMessageEvent):
        """
        格式：/你是则批 @xxx 昵称
        """
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此指令。")
            return

        target_id, nickname = self._get_at_info(event)
        
        # 校验：必须有 @ 且必须有昵称
        if not target_id or not nickname:
            yield event.plain_result("格式不正确！\n请使用格式：/你是则批 @某人 机签/昵称\n例如：/你是则批 @xxx 昵称或机签")
            return

        gid_str = str(group_id)
        target_id_str = str(target_id)

        # 初始化群数据
        if gid_str not in self.data:
            self.data[gid_str] = {}

        # 更新/添加数据
        # 即使已存在，也更新昵称
        self.data[gid_str][target_id_str] = nickname
        self._save_data()
        
        yield event.plain_result(f"认证成功！已记录则批：{nickname} ({target_id})")

    @filter.command("开除则籍")
    async def remove_zepi(self, event: AstrMessageEvent):
        """
        格式：/开除则籍 @xxx
        """
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此指令。")
            return

        # 复用 _get_at_info，这里不需要昵称，只要 target_id
        target_id, _ = self._get_at_info(event)
        
        if not target_id:
            yield event.plain_result("请@一名用户以开除其则籍。")
            return

        gid_str = str(group_id)
        target_id_str = str(target_id)

        if gid_str not in self.data or target_id_str not in self.data[gid_str]:
            yield event.plain_result("该用户不在本群的则批列表中。")
            return

        # 移除并保存
        del self.data[gid_str][target_id_str]
        self._save_data()

        yield event.plain_result(f"操作成功！已将 {target_id} 开除则籍。")

    def _build_call_chain(self, header_text: str, user_dict: Dict[str, str]) -> List:
        """构造换行显示的呼叫消息链"""
        chain = [Plain(header_text + "\n")]
        
        for uid_str, nickname in user_dict.items():
            chain.append(At(qq=int(uid_str)))
            chain.append(Plain(f" （{nickname}）\n"))
            
        return chain

    @filter.command("则批列表")
    async def list_zepi(self, event: AstrMessageEvent):
        """列出本群所有则批，带换行"""
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此指令。")
            return

        gid_str = str(group_id)
        if gid_str not in self.data or not self.data[gid_str]:
            yield event.plain_result("本群目前还没有认证的则批。")
            return

        user_dict = self.data[gid_str]
        
        # 使用辅助方法构造消息链
        chain = self._build_call_chain(f"本群共有{len(user_dict)}位则批：", user_dict)
        yield event.chain_result(chain)

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def check_ymyz_alert(self, event: AstrMessageEvent):
        """
        关键词检测
        """
        text = event.message_str
        if not text:
            return

        has_ymyz = "ymyz" in text.lower()
        ip_pattern = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}"
        has_ip = re.search(ip_pattern, text)

        if has_ymyz or has_ip:
            group_id = event.get_group_id()
            if not group_id:
                return

            gid_str = str(group_id)
            user_dict = self.data.get(gid_str, {})

            if not user_dict:
                return

            # 使用辅助方法构造消息链
            chain = self._build_call_chain("全网呼叫则则人", user_dict)
            yield event.chain_result(chain)