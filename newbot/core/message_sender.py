import requests
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class Target:
    user_id: int
    group_id: int = 0
    is_group: bool = False

    @classmethod
    def from_data(cls, data: Dict[str, Any]) -> "Target":
        msg_type = data.get("message_type", "")
        if msg_type == "group":
            return cls(
                user_id=data["user_id"],
                group_id=data["group_id"],
                is_group=True
            )
        return cls(
            user_id=data["user_id"],
            group_id=0,
            is_group=False
        )


class MessageSender:
    def __init__(self, base_url: str = "http://localhost:3000"):
        self._base_url = base_url.rstrip("/")

    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Optional[requests.Response]:
        try:
            return requests.post(f"{self._base_url}/{endpoint}", json=payload)
        except requests.RequestException as e:
            print(f"[MessageSender] Request failed: {e}")
            return None

    def _send_to_target(self, target: Target, message_segment: Dict[str, Any]) -> Optional[requests.Response]:
        if target.is_group:
            return self._post("send_group_msg", {
                "group_id": target.group_id,
                "message": [message_segment]
            })
        return self._post("send_private_msg", {
            "user_id": target.user_id,
            "message": [message_segment]
        })

    def _build_text_segment(self, text: str, at_user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        segments = []
        if at_user_id is not None:
            segments.append({"type": "at", "data": {"qq": at_user_id}})
        segments.append({"type": "text", "data": {"text": text if at_user_id is None else f" {text}"}})
        return segments

    def send_text(self, target: Target, text: str, at_user_id: Optional[int] = None) -> None:
        if not text:
            return
        if at_user_id is not None:
            self._send_segments(target, self._build_text_segment(text, at_user_id))
        else:
            self._send_to_target(target, {"type": "text", "data": {"text": text}})

    def reply(self, ctx, text: str) -> None:
        """按指令上下文回复到对应会话（私聊/群）"""
        self.send_text(Target.from_data(ctx.raw_data), text)

    def send_text_to_group_with_at(self, group_id: int, user_id: int, text: str) -> None:
        self.send_text(Target(user_id=user_id, group_id=group_id, is_group=True), text, at_user_id=user_id)

    def send_image(self, target: Target, file_path: str) -> None:
        if not file_path:
            return
        self._send_to_target(target, {"type": "image", "data": {"file": file_path}})

    def send_video(self, target: Target, file_path: str) -> None:
        if not file_path:
            return
        self._send_to_target(target, {"type": "video", "data": {"file": file_path}})

    def send_voice(self, target: Target, file_path: str) -> None:
        if not file_path:
            return
        self._send_to_target(target, {"type": "record", "data": {"file": file_path}})

    def _send_segments(self, target: Target, segments: List[Dict[str, Any]]) -> None:
        if target.is_group:
            self._post("send_group_msg", {
                "group_id": target.group_id,
                "message": segments
            })
        else:
            self._post("send_private_msg", {
                "user_id": target.user_id,
                "message": segments
            })

    def send_poke_to_group(self, user_id: int, group_id: int) -> None:
        self._post("group_poke", {"group_id": group_id, "user_id": user_id})

    def send_poke_to_private(self, user_id: int) -> None:
        self._post("friend_poke", {"user_id": user_id})

    def get_group_members(self, group_id: int) -> Optional[requests.Response]:
        return self._post("get_group_member_list", {"group_id": group_id, "no_cache": True})
