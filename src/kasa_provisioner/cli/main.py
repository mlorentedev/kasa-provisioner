"""Typer CLI entry point for kasa-provisioner."""

import asyncio
import logging
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from kasa_provisioner.application.bootstrap import BootstrapUseCase
from kasa_provisioner.application.control import ControlUseCase
from kasa_provisioner.application.discovery import DiscoveryUseCase
from kasa_provisioner.domain.exceptions import KasaProvisionerError
from kasa_provisioner.domain.models import DeviceInfo, PowerCommand, ProtocolType, WifiConfig

app = typer.Typer(
    name="kasa-provisioner",
    help="Offline provisioning and local control of TP-Link smart plugs.",
    no_args_is_help=True,
)
console = Console()


class _MinLevelFilter(logging.Filter):
    """Pass only records at or above min_level — applied at handler level,
    bypassing the per-logger isEnabledFor cache that python-kasa seeds at import."""

    def __init__(self, min_level: int) -> None:
        super().__init__()
        self._min = min_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= self._min


def _configure_logging(verbose: bool) -> None:
    min_level = logging.DEBUG if verbose else logging.ERROR
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    handler.addFilter(_MinLevelFilter(min_level))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)  # root passes everything; the filter decides


@app.command()
def bootstrap(
    ssid: Annotated[str, typer.Option("--ssid", help="Target WiFi SSID")] = "",
    password: Annotated[str, typer.Option("--password", help="Target WiFi WPA2 password")] = "",
    host: Annotated[str, typer.Option("--host", help="Device AP IP")] = "192.168.0.1",
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Provision a factory-fresh device: inject WiFi credentials via its bootstrap AP."""
    _configure_logging(verbose)
    if not ssid or not password:
        console.print("[bold red]Error:[/] --ssid and --password are required")
        raise typer.Exit(1)
    wifi = WifiConfig(ssid=ssid, password=password)
    use_case = BootstrapUseCase(ap_host=host)

    with console.status(f"[bold cyan]Provisioning device at {host}..."):
        try:
            result = asyncio.run(use_case.run(wifi))
        except KasaProvisionerError as exc:
            console.print(f"[bold red]Error:[/] {exc}")
            raise typer.Exit(1) from exc

    console.print(f"[bold green]✓[/] {result.message}")
    console.print(f"  Model: {result.device.model}  MAC: {result.device.mac}")


@app.command()
def discover(
    username: Annotated[str, typer.Option("--username", help="TP-Link account (for KLAP devices)")] = "",
    password: Annotated[str, typer.Option("--password", help="TP-Link password (for KLAP devices)")] = "",
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Discover TP-Link devices on the local network and save registry."""
    _configure_logging(verbose)
    use_case = DiscoveryUseCase(username=username, password=password)

    with console.status("[bold cyan]Scanning LAN..."):
        try:
            devices = asyncio.run(use_case.run())
        except KasaProvisionerError as exc:
            console.print(f"[bold red]Error:[/] {exc}")
            raise typer.Exit(1) from exc

    _render_device_table(devices)


@app.command()
def control(
    host: Annotated[str, typer.Argument(help="Device IP address")],
    command: Annotated[str, typer.Argument(help="on | off | toggle")],
    protocol: Annotated[str, typer.Option("--protocol", help="Protocol: legacy | klap_v1 | klap_v2")] = "legacy",
    username: Annotated[str, typer.Option("--username", help="KLAP username")] = "",
    password: Annotated[str, typer.Option("--password", help="KLAP password")] = "",
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Send a power command (on/off/toggle) to a device by IP."""
    _configure_logging(verbose)

    try:
        cmd = PowerCommand(command)
        proto = ProtocolType(protocol)
    except ValueError as exc:
        console.print(f"[bold red]Error:[/] {exc}")
        raise typer.Exit(1) from exc

    use_case = ControlUseCase(host=host, protocol=proto, username=username, password=password)

    with console.status(f"[bold cyan]{cmd.upper()} → {host}..."):
        try:
            result = asyncio.run(use_case.run(cmd))
        except KasaProvisionerError as exc:
            console.print(f"[bold red]Error:[/] {exc}")
            raise typer.Exit(1) from exc

    state_color = "green" if result.new_state.value == "on" else "yellow"
    console.print(
        f"[bold {state_color}]{result.new_state.upper()}[/] "
        f"(was {result.previous_state}) — {host}"
    )


@app.command()
def status(
    host: Annotated[str, typer.Argument(help="Device IP address")],
    protocol: Annotated[str, typer.Option("--protocol", help="Protocol: legacy | klap_v1 | klap_v2")] = "legacy",
    username: Annotated[str, typer.Option("--username", help="KLAP username")] = "",
    password: Annotated[str, typer.Option("--password", help="KLAP password")] = "",
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Read the current power state of a device without changing it."""
    _configure_logging(verbose)

    try:
        proto = ProtocolType(protocol)
    except ValueError as exc:
        console.print(f"[bold red]Error:[/] {exc}")
        raise typer.Exit(1) from exc

    use_case = ControlUseCase(host=host, protocol=proto, username=username, password=password)

    with console.status(f"[bold cyan]Reading {host}..."):
        try:
            result = asyncio.run(use_case.get_status())
        except KasaProvisionerError as exc:
            console.print(f"[bold red]Error:[/] {exc}")
            raise typer.Exit(1) from exc

    state_color = "green" if result.state.value == "on" else "yellow"
    console.print(
        f"{host}  [{state_color}]{result.state.upper()}[/{state_color}]"
        + (f"  (uptime: {_fmt_uptime(result.on_time_secs)})" if result.on_time_secs else "")
    )


def _fmt_uptime(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m"
    return f"{m}m {s}s"


def _render_device_table(devices: list[DeviceInfo]) -> None:
    table = Table(title=f"Found {len(devices)} device(s)")
    table.add_column("Host", style="cyan")
    table.add_column("Model")
    table.add_column("Protocol", style="magenta")
    table.add_column("Alias")
    table.add_column("MAC")

    for d in devices:
        table.add_row(d.host, d.model or "—", d.protocol, d.alias or "—", d.mac or "—")

    console.print(table)
