from pathlib import Path
from collections.abc import Sequence
from typing import Any

import click

from boss_agent_cli import __version__
from boss_agent_cli.api.browser_source import POLICIES as BROWSER_SOURCES
from boss_agent_cli.commands.register import register_candidate_commands, register_recruiter_commands
from boss_agent_cli.config import load_config
from boss_agent_cli.hooks import create_hook_bus
from boss_agent_cli.output import emit_error, Logger
from boss_agent_cli.platforms import list_platforms


class BossCliGroup(click.Group):
	"""Click group that preserves the JSON envelope contract for usage errors."""

	def main(
		self,
		args: Sequence[str] | None = None,
		prog_name: str | None = None,
		complete_var: str | None = None,
		standalone_mode: bool = True,
		**extra: Any,
	) -> Any:
		try:
			return super().main(
				args=args,
				prog_name=prog_name,
				complete_var=complete_var,
				standalone_mode=False,
				**extra,
			)
		except click.ClickException as exc:
			if not standalone_mode:
				raise
			ctx = getattr(exc, "ctx", None)
			command = getattr(ctx, "info_name", None) or self.name or "boss"
			emit_error(
				command,
				code="INVALID_PARAM",
				message=exc.format_message(),
				recoverable=False,
				recovery_action="修正参数",
			)
			return None


@click.group(
	name="boss",
	cls=BossCliGroup,
	invoke_without_command=True,
	no_args_is_help=False,
	context_settings={"allow_interspersed_args": False},
)
@click.version_option(version=__version__, prog_name="boss")
@click.option("--data-dir", default="~/.boss-agent", help="数据存储目录")
@click.option("--delay", default=None, help="请求间隔范围（秒），如 1.5-3.0")
@click.option("--cdp-url", default=None, help="Chrome CDP 调试地址（如 http://localhost:9222），启用则优先用用户 Chrome")
@click.option("--browser-source", default=None, type=click.Choice(list(BROWSER_SOURCES)), help="浏览器通道来源：auto（默认，允许降级）/ existing-browser（复用现有浏览器）/ stored-cookie（fail-closed，只连指定 CDP，不降级）")
@click.option("--platform", "platform_name", default=None, help="指定招聘平台适配器（默认 zhipin，即 BOSS 直聘）")
@click.option("--role", default=None, type=click.Choice(["candidate", "recruiter"]), help="角色模式：candidate（求职者，默认）/ recruiter（招聘者）")
@click.option("--log-level", default=None, type=click.Choice(["error", "warning", "info", "debug"]))
@click.option("--json/--no-json", "json_output", default=False, help="强制 JSON 输出（即使在终端中）")
@click.pass_context
def cli(ctx: click.Context, data_dir: str, delay: str | None, cdp_url: str | None, browser_source: str | None, platform_name: str | None, role: str | None, log_level: str | None, json_output: bool) -> None:
	ctx.ensure_object(dict)
	resolved_dir = Path(data_dir).expanduser()
	resolved_dir.mkdir(parents=True, exist_ok=True)
	ctx.obj["data_dir"] = resolved_dir
	ctx.obj["json_output"] = json_output

	cfg = load_config(resolved_dir / "config.json")

	if delay:
		try:
			low, high = delay.split("-", 1)
			ctx.obj["delay"] = (float(low), float(high))
		except ValueError as exc:
			raise click.BadParameter(
				"delay must be a range like 1.5-3.0",
				param_hint="--delay",
			) from exc
	else:
		ctx.obj["delay"] = tuple(cfg["request_delay"])

	level = log_level or cfg["log_level"]
	ctx.obj["log_level"] = level
	ctx.obj["logger"] = Logger(level)
	ctx.obj["cdp_url"] = cdp_url or cfg.get("cdp_url")

	# 归一化（大小写/首尾空白）后再校验，与下游 resolve_policy 的 .strip().lower() 一致，
	# 避免 config.json 里 "Auto" / " stored-cookie " 这类值被 CLI 拒绝、策略层却接受的不一致。
	resolved_browser_source = (browser_source or cfg.get("browser_source") or "auto").strip().lower()
	if resolved_browser_source not in BROWSER_SOURCES:
		raise click.BadParameter(
			f"unknown browser source {resolved_browser_source!r}, supported: {', '.join(BROWSER_SOURCES)}",
			param_hint="--browser-source",
		)
	ctx.obj["browser_source"] = resolved_browser_source

	resolved_platform = platform_name or cfg.get("platform") or "zhipin"
	available = list_platforms()
	if resolved_platform not in available:
		raise click.BadParameter(
			f"unknown platform {resolved_platform!r}, supported: {', '.join(available)}",
			param_hint="--platform",
		)
	ctx.obj["platform"] = resolved_platform

	resolved_role = role or cfg.get("role") or "candidate"
	ctx.obj["role"] = resolved_role

	ctx.obj["config"] = cfg
	ctx.obj["hooks"] = create_hook_bus()

	if ctx.invoked_subcommand is None:
		from boss_agent_cli.commands.wizard import run_wizard_command

		run_wizard_command(ctx)


register_candidate_commands(cli)
register_recruiter_commands(cli)
