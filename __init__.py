import json
import re
import subprocess
from collections import namedtuple
from pathlib import Path

from albert import *

md_iid = "4.0"
md_version = "2.5.0"
md_name = "Mullvad"
md_description = "Manage mullvad VPN connections"
md_license = "MIT"
md_url = "https://github.com/albertlauncher/python"
md_authors = ["@Pete-Hamlin"]
md_credits = ["@janeklb", "@Bierchermuesli"]
md_bin_dependencies = ["mullvad"]


class Plugin(PluginInstance, GlobalQueryHandler):
    VPNConnection = namedtuple("VPNConnection", ["name", "connected"])
    blocked_icon = Path(__file__).parent / "lock-10.png"
    connect_icon = Path(__file__).parent / "lock-9.png"
    disconnect_icon = Path(__file__).parent / "lock-1.png"

    def __init__(self):
        PluginInstance.__init__(self)
        GlobalQueryHandler.__init__(self)

        self.connection_regex = re.compile(r"[a-z]{2}-[a-z]*-[a-z]{2,4}-[\d]{2,3}")

    def defaultTrigger(self) -> str:
        return "mullvad "

    def getRelays(self):
        relayStr = subprocess.check_output("mullvad relay list", shell=True, encoding="UTF-8")
        for relayStr in relayStr.splitlines():
            relay = relayStr.split()
            if relay and self.connection_regex.match(relay[0]):
                yield (relay[0], relayStr)

    def parse_status(self) -> tuple[str, callable]:
        status = json.loads(subprocess.check_output("mullvad status -j", shell=True, encoding="UTF-8"))
        state = status.get("state")
        match state:
            case "error":
                substring = "{}: {}".format(state.capitalize(), status["details"]["cause"]["reason"])
                return substring, lambda: makeImageIcon(self.blocked_icon)
            case "disconnected":
                substring = "{}: {} - {}, {}".format(
                    state.capitalize(),
                    status["details"]["location"]["ipv4"],
                    status["details"]["location"]["city"],
                    status["details"]["location"]["country"],
                )
                return substring, lambda: makeImageIcon(self.disconnect_icon)
            case "connected":
                substring = "{} to {}: {} - {}, {}".format(
                    state.capitalize(),
                    status["details"]["location"]["hostname"],
                    status["details"]["location"]["ipv4"],
                    status["details"]["location"]["city"],
                    status["details"]["location"]["country"],
                )
                return substring, lambda: makeImageIcon(self.connect_icon)
            case _:
                return "Unparsable result executiong mullvad status -j", lambda: makeThemeIcon("network-wired")

    def defaultItems(self) -> list[StandardItem]:
        subtext, icon = self.parse_status()
        return [
            StandardItem(
                id="status",
                text="Status",
                subtext=subtext,
                icon_factory=icon,
                actions=[
                    Action(
                        "reconnect",
                        "Reconnect",
                        lambda: runDetachedProcess(["mullvad", "reconnect"]),
                    ),
                    Action(
                        "connect",
                        "Connect",
                        lambda: runDetachedProcess(["mullvad", "connect"]),
                    ),
                    Action(
                        "disconnect",
                        "Disconnect",
                        lambda: runDetachedProcess(["mullvad", "disconnect"]),
                    ),
                ],
            ),
        ]

    def actions(self) -> list[StandardItem]:
        return [
            StandardItem(
                id="connect",
                text="Connect",
                subtext="Connect to default server",
                icon_factory=lambda: makeImageIcon(self.connect_icon),
                actions=[
                    Action(
                        "connect",
                        "Connect",
                        lambda: runDetachedProcess(["mullvad", "connect"]),
                    )
                ],
            ),
            StandardItem(
                id="disconnect",
                text="Disconnect",
                subtext="Disconnect from VPN",
                icon_factory=lambda: makeImageIcon(self.disconnect_icon),
                actions=[
                    Action(
                        "disconnect",
                        "Disconnect",
                        lambda: runDetachedProcess(["mullvad", "disconnect"]),
                    )
                ],
            ),
            StandardItem(
                id="reconnect",
                text="Reconnect",
                subtext="Reconnect to current server",
                icon_factory=lambda: makeImageIcon(self.blocked_icon),
                actions=[
                    Action(
                        "reconnect",
                        "Reconnect",
                        lambda: runDetachedProcess(["mullvad", "reconnect"]),
                    )
                ],
            ),
        ]

    def buildItem(self, relay):
        name = relay[0]
        command = ["mullvad", "relay", "set", "location", name]
        subtext = relay[1]
        return StandardItem(
            id=f"vpn-{name}",
            text=name,
            subtext=subtext,
            icon_factory=lambda: makeThemeIcon("network-wired"),
            actions=[
                Action(
                    "connect",
                    text="Connect",
                    callable=lambda: runDetachedProcess(command),
                ),
                Action("copy", "Copy to Clipboard", lambda t=name: setClipboardText(t)),
            ],
        )

    def handleTriggerQuery(self, query):
        if query.isValid:
            if query.string.strip():
                relays = self.getRelays()
                query.add([item for item in self.actions() if query.string.lower() in item.text.lower()])
                query.add(
                    [
                        self.buildItem(relay)
                        for relay in relays
                        if all(q in relay[0].lower() for q in query.string.lower().split())
                    ]
                )
            else:
                query.add(self.defaultItems())

    def handleGlobalQuery(self, query):
        if query.string.strip():
            return [
                RankItem(item=item, score=0) for item in self.actions() if query.string.lower() in item.text.lower()
            ]
        else:
            return []
