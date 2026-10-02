from typing import Callable, List, Dict, Any, Optional, Set


class CommandContext:
    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.message_id = data.get("message_id", 0)
        self.raw_message = data.get("raw_message", "")
        self.user_id = data.get("user_id", 0)
        self.user_name = data.get("sender", {}).get("nickname", "")
        self.message_type = data.get("message_type", "")
        self.group_id = data.get("group_id", 0)
        self.is_group = self.message_type == "group"
        self.is_private = self.message_type == "private"
        self.sender_nickname = data.get("sender", {}).get("nickname", "")

    def get_target_data(self) -> Dict[str, Any]:
        return self.raw_data

    def split_message(self) -> tuple:
        parts = self.raw_message.split(" ", 1)
        if len(parts) > 1:
            parts[1] = parts[1].strip()
        return tuple(parts)

    def get_instruction(self) -> str:
        return self.raw_message.split(" ", 1)[0].lower()

    def get_args(self) -> str:
        parts = self.raw_message.split(" ", 1)
        return parts[1].strip() if len(parts) > 1 else ""


class Command:
    def __init__(self, names: List[str], handler: Callable,
                 description: str = "", is_async: bool = False,
                 permission_check: Optional[Callable] = None):
        self.names = [n.lower() for n in names]
        self.handler = handler
        self.description = description
        self.is_async = is_async
        self.permission_check = permission_check

    def can_execute(self, ctx: CommandContext) -> bool:
        if self.permission_check is None:
            return True
        return self.permission_check(ctx)

    def execute(self, ctx: CommandContext, *args, **kwargs) -> Any:
        if not self.can_execute(ctx):
            return None
        return self.handler(ctx, *args, **kwargs)


class CommandRouter:
    def __init__(self):
        self._commands: Dict[str, Command] = {}
        self._aliases: Dict[str, str] = {}

    def register(self, names: List[str], handler: Callable,
                 description: str = "", is_async: bool = False,
                 permission_check: Optional[Callable] = None) -> None:
        cmd = Command(names, handler, description, is_async, permission_check)
        primary = names[0].lower()
        self._commands[primary] = cmd
        for name in names:
            self._aliases[name.lower()] = primary

    def add_command(self, command: Command) -> None:
        primary = command.names[0]
        self._commands[primary] = command
        for name in command.names:
            self._aliases[name] = primary

    def find_command(self, instruction: str) -> Optional[Command]:
        instruction = instruction.lower()
        primary = self._aliases.get(instruction)
        if primary:
            return self._commands.get(primary)
        return None

    def execute(self, ctx: CommandContext) -> bool:
        instruction = ctx.get_instruction()
        cmd = self.find_command(instruction)
        if cmd is None:
            return False
        cmd.execute(ctx)
        return True

    def get_all_commands(self) -> List[Command]:
        return list(self._commands.values())

    def get_help_text(self) -> str:
        lines = ["指令简介"]
        for cmd in self._commands.values():
            names = "/".join(cmd.names[:3])
            lines.append(f"  {names} - {cmd.description}")
        return "\n".join(lines)
