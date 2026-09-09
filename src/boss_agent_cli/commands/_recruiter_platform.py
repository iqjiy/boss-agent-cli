"""Recruiter Platform 实例化辅助函数。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from boss_agent_cli.api.browser_source import BrowserSourceUnsupported, resolve_policy
from boss_agent_cli.api.recruiter_client import BossRecruiterClient
from boss_agent_cli.platforms import get_recruiter_platform
from boss_agent_cli.platforms.recruiter_base import RecruiterPlatform

if TYPE_CHECKING:
	import click
	from boss_agent_cli.auth.manager import AuthManager


def get_recruiter_platform_instance(ctx: "click.Context", auth: "AuthManager") -> RecruiterPlatform:
	obj = ctx.obj or {}
	return build_recruiter_platform_instance(
		obj.get("platform") or "zhipin",
		auth,
		delay=obj.get("delay", (1.5, 3.0)),
		cdp_url=obj.get("cdp_url"),
		browser_source=obj.get("browser_source"),
	)


def build_recruiter_platform_instance(
	name: str,
	auth: "AuthManager",
	*,
	delay: tuple[float, float] = (1.5, 3.0),
	cdp_url: str | None = None,
	browser_source: str | None = None,
) -> RecruiterPlatform:
	"""Build a recruiter platform without requiring a Click context.

	非 ``auto`` 来源只对有浏览器通道的 zhipin 招聘者 client 有意义；其余平台
	没有招聘者浏览器通道，显式抛 ``BrowserSourceUnsupported``（命令层转
	``NOT_SUPPORTED``），与 ``_platform._build_client`` 同一写法。
	"""
	policy = resolve_policy(browser_source)
	# 守卫必须先于 get_recruiter_platform：非 zhipin 平台未注册 recruiter 适配器，
	# 晚判会被 registry 的 ValueError 抢先，BrowserSourceUnsupported 永远到不了。
	if name != "zhipin" and policy.fail_closed:
		raise BrowserSourceUnsupported(name, policy.name)
	recruiter_name = f"{name}-recruiter"
	plat_cls = get_recruiter_platform(recruiter_name)
	client = BossRecruiterClient(auth, delay=delay, cdp_url=cdp_url, browser_source=policy.name)
	return plat_cls(client)


__all__ = ["build_recruiter_platform_instance", "get_recruiter_platform_instance"]
