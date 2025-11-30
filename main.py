import os
import json
from typing import Dict, List, Optional

from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger
from astrbot.api.message_components import At, Plain

@register("astrbot_plugin_ymyz", "Taropoi", "东方绯想天则玩家管理插件", "1.0.0", "https://github.com/waterladleh/astrbot_plugin_ymyz")
class ZePiPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 获取插件数据的标准存储目录
        # 修正：直接传入插件名称字符串 "astrbot_plugin_ymyz"
        self.data_dir = StarTools.get_data_dir("astrbot_plugin_ymyz")
        self.data_file = os.path.join(self.data_dir, "zepi_list.json")
        
        # 加载数据
        self.data = self._load_data()
        logger.info(f"则批管理插件已加载，数据路径: {self.data_file}")

    def _load_data(self) -> Dict[str, List[int]]:
        """加载数据，如果文件不存在则返回空字典"""
        if not os.path.exists(self.data_file):
            return {}
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
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

    def _get_mentioned_user(self, event: AstrMessageEvent) -> Optional[int]:
        """从消息中解析被 @ 的用户 ID"""
        # 遍历消息链寻找 At 类型的组件
        for component in event.message_obj.message:
            # 情况1: 标准 AstrBot At 组件对象
            if isinstance(component, At):
                # 排除 @全体成员
                if component.qq and str(component.qq) != "all":
                    return int(component.qq)
            
            # 情况2: 字典格式 (兼容部分旧逻辑或原始数据)
            elif isinstance(component, dict) and component.get("type") == "at":
                data = component.get("data", {})
                qq = data.get("qq")
                if qq and str(qq) != "all":
                    return int(qq)

            # 情况3: 其他对象格式 (尝试读取 type 和 qq 属性)
            elif hasattr(component, "type") and getattr(component, "type") == "at":
                if hasattr(component, "qq"):
                    qq = getattr(component, "qq")
                    if qq and str(qq) != "all":
                        return int(qq)
                        
        return None

    @filter.command("你是则批")
    async def add_zepi(self, event: AstrMessageEvent):
        """将 @ 的用户添加到本群则批列表"""
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此指令。")
            return

        target_id = self._get_mentioned_user(event)
        if not target_id:
            yield event.plain_result("请 @ 一名用户将其认证为则批。")
            return

        # 确保该群数据存在
        gid_str = str(group_id)
        if gid_str not in self.data:
            self.data[gid_str] = []

        # 检查是否已存在
        if target_id in self.data[gid_str]:
            yield event.plain_result("该用户已经是公认的则批了，无需重复认证。")
            return

        # 添加并保存
        self.data[gid_str].append(target_id)
        self._save_data()
        
        yield event.plain_result(f"认证成功！已将 {target_id} 加入本群则批豪华午餐。")

    @filter.command("开除则籍")
    async def remove_zepi(self, event: AstrMessageEvent):
        """将 @ 的用户从本群则批列表移除"""
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此指令。")
            return

        target_id = self._get_mentioned_user(event)
        if not target_id:
            yield event.plain_result("请 @ 一名用户以开除其则籍。")
            return

        gid_str = str(group_id)
        if gid_str not in self.data or target_id not in self.data[gid_str]:
            yield event.plain_result("该用户不在本群的则批列表中。")
            return

        # 移除并保存
        self.data[gid_str].remove(target_id)
        self._save_data()

        yield event.plain_result(f"操作成功！已将 {target_id} 开除则籍。")

    @filter.command("则批列表")
    async def list_zepi(self, event: AstrMessageEvent):
        """列出本群所有则批"""
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此指令。")
            return

        gid_str = str(group_id)
        if gid_str not in self.data or not self.data[gid_str]:
            yield event.plain_result("本群目前还没有认证的则批。")
            return

        user_list = self.data[gid_str]
        
        # 构造回复消息链
        chain = [Plain(f"本群共有 {len(user_list)} 位则批：\n")]
        
        for uid in user_list:
            chain.append(At(qq=uid))
            chain.append(Plain("\n"))
            
        # 发送消息链
        yield event.chain_result(chain)