#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright © 2025 Martine S. Lenders <martine.lenders@tu-dresden.de>
#
# Distributed under terms of the MIT license.

import argparse
import asyncio
import collections
import enum
import fcntl
import functools
import importlib
import ipaddress
import logging
import pathlib
import psutil
import os
import socket
import struct
import sys


from scapy.all import IPv6, load_contrib

SCRIPT_PATH = pathlib.Path(__file__).resolve().parent
OPENSCHC_PATH = SCRIPT_PATH / "openschc" / "src"

ETHERNET_PDU = 1500
DEFAULT_PDU = ETHERNET_PDU
DEFAULT_DUTY_CYCLE = 500


class AsyncInterface:
    @staticmethod
    def _run_async(func):
        @functools.wraps(func)
        async def run(*args, loop=None, executor=None, **kwargs):
            if loop is None:
                loop = asyncio.get_event_loop()
            pfunc = functools.partial(func, *args, **kwargs)
            return await loop.run_in_executor(executor, pfunc)

        return run

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()


class TunTapType(enum.Enum):
    TUN = 1
    TAP = 2


class TunTap(AsyncInterface):
    TUNSETIFF = 0x400454CA
    IFF_TUN = 0x0001
    IFF_TAP = 0x0002
    IFF_NO_PI = 0x1000

    # based on pytuntap implementation, but adopted for asyncio
    # https://github.com/gonewind73/pytuntap/blob/master/tuntap.py
    def __init__(self, name=None, nic_type=TunTapType.TUN):
        self._name = name
        self._nic_type = nic_type
        self.addrs = []
        self._handle = None
        self.created = False

    @property
    def name(self):
        return self._name

    @property
    def nic_type(self):
        return self._nic_type

    def _get_fd(self):
        # pytest crashes with -s if we patch os.open ;-), so provide wrapper to patch
        return self._run_async(os.open)("/dev/net/tun", os.O_RDWR)  # pragma: no cover

    async def create(self):
        if self._handle:
            raise FileExistsError("Interface is already open")
        if self.name:
            proc = await asyncio.create_subprocess_exec(
                "ip",
                "link",
                "show",
                "dev",
                self.name,
                stdout=asyncio.subprocess.DEVNULL,
            )
            ret = await proc.wait()
        else:
            ret = -1
        if ret != 0:
            self.created = True
        # Open TUN device file.
        tun = await self._get_fd()
        if not tun:
            raise IOError("Unable to open /dev/net/tun")
        # Tall it we want a TUN device named tun0.
        flags = self.IFF_NO_PI
        if self.nic_type == TunTapType.TUN:  # noqa: E721 false positive
            flags |= self.IFF_TUN
        elif self.nic_type == TunTapType.TAP:  # noqa: E721 false positive
            flags |= self.IFF_TAP
        else:
            raise ValueError(f"Unknown tuntap type {self.nic_type}")
        if self.name:
            ifr_name = self.name.encode() + b"\x00" * (16 - len(self.name.encode()))
        else:
            ifr_name = b"\x00" * 16
        ifr = struct.pack("16sH22s", ifr_name, flags, b"\x00" * 22)
        ret = await self._run_async(fcntl.ioctl)(tun, self.TUNSETIFF, ifr)
        dev, _ = struct.unpack("16sH", ret[:18])
        dev = dev.decode().strip("\x00")
        self._name = dev
        self._handle = tun
        proc = await asyncio.create_subprocess_exec(
            "ip", "link", "show", "dev", self.name, stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if "state UP" not in stdout.decode():
            await asyncio.create_subprocess_exec(
                "ip", "link", "set", "up", "dev", self.name
            )
        return self

    async def add_addr(self, addr):
        proc = await asyncio.create_subprocess_exec(
            "ip", "addr", "add", addr, "dev", self.name
        )
        await proc.wait()
        if proc.returncode == 0:
            self.addrs.append(addr)

    async def open(self):
        if self._handle is None:
            await self.create()

    async def close(self):
        await self._run_async(os.close)(self._handle)
        await asyncio.sleep(1)
        self._handle = None
        if self.created:
            mode = "tun" if self.nic_type == TunTapType.TUN else "tap"  # noqa: E721
            await asyncio.create_subprocess_exec(
                "ip",
                "tuntap",
                "delete",
                "mode",
                mode,
                self.name,
                stderr=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
            )

    async def read(self):
        return await self._run_async(os.read)(self._handle, ETHERNET_PDU)

    async def write(self, data):
        return await self._run_async(os.write)(self._handle, data)

    async def recv(self):
        if self._handle is None:
            raise ConnectionError("TUN is not connected")
        return None, await self.read()

    async def send(self, address, buf):
        # pylint: disable=unused-argument
        if self._handle is None:
            raise ConnectionError("TUN is not connected")
        await self.write(buf)


class NorthInterface(TunTap):
    @property
    def pdu(self):
        return 1486


class SCHCEncInterface(AsyncInterface):
    DEFAULT_ETHERTYPE = 0x88B5  # local experimental ethertype
    ETHERNET_HDR_FMT = "!6s6sH"  # 6 byte source address, 6 byte dest, 2 byte ethertype
    ETHERNET_HDR_LEN = 14

    def __init__(
        self, name, ethertype=DEFAULT_ETHERTYPE, pdu=1500, duty_cycle=500
    ):
        super().__init__()
        self._iface_name = name
        self._duty_cycle = duty_cycle
        self._pdu = pdu
        self._sock = None
        self._mac_addr = None
        self.ethertype = ethertype
        self.loop = None

    @property
    def pdu(self):
        return self._pdu

    @property
    def duty_cycle(self):
        return self._duty_cycle

    @property
    def mac_addr(self):
        return self._mac_addr

    def etherhdr(self, address):
        if address is None:
            address = b"\xff" * 6
        return struct.pack(
            self.ETHERNET_HDR_FMT, address, self._mac_addr, self.ethertype
        )

    async def open(self):
        self.loop = asyncio.get_event_loop()
        self._sock = await self._run_async(socket.socket)(
            socket.AF_PACKET, socket.SOCK_RAW, self.ethertype
        )
        self._sock.setblocking(False)
        for key, value in psutil.net_if_addrs().items():
            if self._iface_name == key:
                for item in value:
                    if item.family == socket.AF_PACKET:
                        self._mac_addr = bytes.fromhex(item.address.replace(":", ""))
                        break
        assert self._mac_addr, f"No MAC address found for interface {self._iface_name}"
        self._sock.bind((self._iface_name, self.ethertype))

    async def close(self):
        if self._sock:
            await self._run_async(self._sock.close)()
        self._sock = None
        self._mac_addr = None

    async def send(self, address, buf):
        if self._sock is None:
            raise ConnectionError("Interface is not opened")
        return await self.loop.sock_sendall(self._sock, self.etherhdr(address) + buf)

    async def recv(self):
        if self._sock is None:
            raise ConnectionError("Interface is not opened")
        data = await self.loop.sock_recv(self._sock, self.ETHERNET_HDR_LEN + self._pdu)
        assert len(data) >= self.ETHERNET_HDR_LEN
        dst, src, ethertype = struct.unpack(
            self.ETHERNET_HDR_FMT, data[: self.ETHERNET_HDR_LEN]
        )
        assert ethertype == self.ethertype
        assert self._mac_addr and self._mac_addr == dst
        return src, data[self.ETHERNET_HDR_LEN :]


class OpenSCHCLoader:
    def __init__(self, openschc_path: str | pathlib.Path):
        self.openschc_path = openschc_path
        if str(self.openschc_path) not in sys.path:
            sys.path.append(str(self.openschc_path))
        self.architecture = importlib.import_module("architecture")
        self.protocol = importlib.import_module("protocol")
        self.gen_rulemanager = importlib.import_module("gen_rulemanager")

    def get_rule_manager(self, *args, **kwargs):
        return self.gen_rulemanager.RuleManager(*args, **kwargs)

    def get_protocol(self, *args, **kwargs):
        return self.protocol.SCHCProtocol(*args, **kwargs)


class IoTSCHCSystem:
    def __init__(self, logger: logging.Logger = None, debug: bool = False):
        loop = asyncio.get_event_loop()
        loop.set_debug(debug)
        self.scheduler = IoTSCHCScheduler(self, loop)
        if logger is None:
            self.logger = logging.getLogger(__name__)
        else:
            self.logger = logger
        logging.basicConfig()
        self.debug = debug
        if debug:
            self.logger.setLevel(logging.DEBUG)

    def get_scheduler(self):
        return self.scheduler

    def log(self, name, message):
        self.logger.debug("%s %s", name, message)


class IoTSCHCScheduler:
    def __init__(self, system, loop):
        self.loop = loop
        self.system = system
        self.sessions = collections.defaultdict(list)

    def get_clock(self):
        return self.loop.time()

    def add_event(self, time_in_sec, event_function, event_args, session_id=None):
        # self.system.log(
        print(
            canon_name(type(self)),
            f"Add event: call {canon_name(event_function)} with {event_args} "
            f"in {time_in_sec} sec",
        )
        assert time_in_sec >= 0
        if event_args is None:
            event_args = []
        self.session_id = session_id

        def event_wrapper(*event_args):
            event_function(*event_args)
            if handler in self.sessions[session_id]:
                self.sessions[session_id].remove(handler)

        handler = self.loop.call_later(
            time_in_sec,
            event_wrapper,
            *event_args,
        )

    def cancel_event(self, event_handle):
        self.system.log(canon_name(type(self)), f"Cancel event {event_handle}")
        event_handle.cancel()

    def _cancel_session(self, session_id):
        for task in self.sessions[session_id]:
            task.cancel()

    def cancel_session(self, session_id=None):
        if session_id is None:
            for session_id in self.sessions:
                self._cancel_session(session_id)
        else:
            self._cancel_session(session_id)


class IoTSCHCUpperLayer:
    def __init__(self,
        system: IoTSCHCSystem,
        north_iface: NorthInterface,
        is_device: bool = True,
        route_file: pathlib.Path = None,
    ):
        self.north_iface = north_iface
        self.system = system
        self.is_device = is_device
        self._protocol = None
        self._route_file = route_file
        self._routes = {}
        self.address = None

    def iterate_route_file(self):
        if self._route_file is not None and self._route_file.exists():
            with open(self._route_file) as f:
                for line in f:
                    ip_addr_str, mac_str = line.strip().split("=")
                    ip_addr_str = ip_addr_str.split("/")[0]
                    ip_addr = ipaddress.ip_address(ip_addr_str).packed
                    mac_addr = bytes.fromhex(mac_str.strip())
                    self._routes[ip_addr] = mac_addr
                    yield ip_addr_str, ip_addr, mac_addr

    def route(self, l3_addr):  # pylint: disable=unused-argument
        if l3_addr in self._routes:
            return self._routes[l3_addr]

        if self._route_file is None:
            return None

        for _, ip_addr, mac_addr in self.iterate_route_file():
            if ip_addr == l3_addr:
                return mac_addr
        return None

    @property
    def protocol(self):
        return self._protocol

    @protocol.setter
    def protocol(self, prot):
        self._protocol = prot

    async def send_north(self, address: bytes, raw_packet: bytes):
        self.system.log(
            canon_name(type(self)),
            f"send_north from address={address} raw_packet={IPv6(raw_packet)!r}",
        )
        try:
            await self.north_iface.send(address, raw_packet)
        except OSError as exc:
            if exc.errno == errno.EINVAL:
                self.system.log(canon_name(type(self)), "Invalid packet")

    async def send_packet(self, packet: bytes, address: bytes = None):
        if address is None:
            if (packet[0] & 0xF0) == 0x60 and len(packet) > 40:
                # try to guess address based on routing IPv6 address
                dst_l3_addr = packet[24:40]
                address = self.route(dst_l3_addr)
        if self.is_device:
            kwargs = {"core_id": address, "device_id": self.address}
        else:
            kwargs = {"device_id": address, "core_id": self.address}
        self.system.log(
            canon_name(type(self)),
            f"Using {kwargs} to send over SCHC",
        )
        self.protocol.schc_send(packet, verbose=self.system.debug, **kwargs)

    async def handle_north(self):
        while True:
            addr, data = await self.north_iface.recv()
            if (data[0] & 0xF0) == 0x60 and len(data) > 4 and data[6] == 58:
                # drop ICMPv6 packets
                self.system.log(canon_name(type(self)), f"Dropped ICMPv6 packet")
                continue
            # self.system.log(
            print(
                canon_name(type(self)), f"Received {IPv6(data)!r} from {addr} from north"
            )
            print(canon_name(type(self)), f"data: {data}")
            self.system.log(canon_name(type(self)), f"data: {data}")
            await self.send_packet(data)


class IoTSCHCLowerLayer:
    def __init__(
        self,
        system: IoTSCHCSystem,
        south_iface: SCHCEncInterface,
        is_device: bool = False
    ):
        self.south_iface = south_iface
        self.system = system
        self.protocol = None
        self.is_device = is_device
        self._north = None

    def _set_protocol(self, prot):
        self.protocol = prot

    @property
    def north(self):
        return self._north

    @north.setter
    def north(self, north: IoTSCHCUpperLayer):
        self._north = north

    def send_packet(self, packet, other_address, transmit_callback=None):
        self.system.log(
            canon_name(type(self)),
            f"send_packet to packet={packet.hex()} other_address={other_address} "
            f"transmit_callback={canon_name(transmit_callback)}",
        )
        self.system.scheduler.loop.create_task(
            self.south_iface.send(other_address, bytes(packet))
        )
        if transmit_callback:
            transmit_callback(1)

    def get_mtu_size(self):
        return self.south_iface.pdu * 8

    async def recv_packet(self, data, src_l2_addr=None, dst_l2_addr=None):
        if self.is_device:
            kwargs = {"core_id": src_l2_addr, "device_id": dst_l2_addr}
        else:
            kwargs = {"device_id": src_l2_addr, "core_id": dst_l2_addr}
        self.system.log(
            canon_name(type(self)),
            f"Using {kwargs} to send over SCHC",
        )
        res = self.protocol.schc_recv(
            bytearray(data),
            verbose=self.system.debug,
            **kwargs,
        )
        schc_addr, schc_data = res if res else (None, None)
        if schc_data:
            await self.north.send_north(schc_addr, bytes(schc_data))

    async def handle_south(self):
        while True:
            addr, data = await self.south_iface.recv()
            self.system.log(
                canon_name(type(self)), f"Received {data} from {addr} from south"
            )
            await self.recv_packet(
                data,
                src_l2_addr=addr,
                dst_l2_addr=self.south_iface.mac_addr
            )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--client",
        help="Configure either as device/client or core/gateway (default).",
        action="store_true",
    )
    parser.add_argument(
        "-d",
        "--duty-cycle",
        help=f"Duty cycle for the south interface (default: {DEFAULT_DUTY_CYCLE})",
        type=int,
        default=DEFAULT_DUTY_CYCLE,
    )
    parser.add_argument(
        "-n",
        "--north-iface",
        help="North TUN interface name (default: tun0)",
        default="tun0",
    )
    parser.add_argument(
        "-r",
        "--route-file",
        help="File that translates IPv6 prefixes to MAC addresses",
        default=None,
        type=pathlib.Path,
    )
    parser.add_argument(
        "-s",
        "--pdu",
        help=f"PDU for the south interface (default: {DEFAULT_PDU})",
        type=int,
        default=DEFAULT_PDU,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Provide debug output",
        action="store_true",
    )
    parser.add_argument(
        "south_iface",
        help="South interface name",
    )
    parser.add_argument(
        "rule_config",
        help="SCHC rule configuration "
        "(see https://openschc.github.io/openschc/Source/gen_rulemanager.html)",
    )
    parser.add_argument(
        "peer_addresses",
        help="IPv6 address of one of the SCHC peers",
        nargs="*",
        metavar="peer_address",
    )
    parser.add_argument(
        "-a",
        "--ipv6-address",
        help="Configure IPv6 addresses for the north interface",
        nargs="*",
        dest="ipv6_addresses",
    )
    args = parser.parse_args()

    load_contrib("coap")
    openschc_loader = OpenSCHCLoader(OPENSCHC_PATH)
    system = IoTSCHCSystem(debug=args.verbose)
    async with (
        # TBD: addrs for NorthInterface?
        NorthInterface(name=args.north_iface) as north,
        SCHCEncInterface(
            name=args.south_iface,
            duty_cycle=args.duty_cycle,
            pdu=args.pdu,
        ) as south,
    ):
        for addr in args.ipv6_addresses:
            await north.add_addr(addr)
        lower = IoTSCHCLowerLayer(system, south, is_device=args.client)
        upper = IoTSCHCUpperLayer(
            system,
            north,
            route_file=args.route_file,
            is_device=args.client
        )
        lower.north = upper
        prot = openschc_loader.get_protocol(
            layer2=lower,
            system=system,
            role=(
                openschc_loader.protocol.T_POSITION_DEVICE
                if args.client
                else openschc_loader.protocol.T_POSITION_CORE
            ),
            config={
                "debug_level": 10 if args.verbose else 0,
                "tx_interval": south.duty_cycle,
            },
            unique_peer=False,
        )
        upper.protocol = prot
        rule_manager = openschc_loader.get_rule_manager()
        added_devices = set()
        peer_addresses = [a.split("/")[0] for a in args.peer_addresses]
        for _ in range(60 // 5):
            for ip_addr, _, mac_addr in upper.iterate_route_file():
                if args.client:
                    ip_candidate = ip_addr not in peer_addresses
                else:
                    ip_candidate = ip_addr in peer_addresses
                if (
                    ip_candidate and ip_addr not in added_devices
                ):
                    rule_manager.Add(
                        device=mac_addr, file=args.rule_config
                    )
                    added_devices.add(ip_addr)
                elif ip_addr in [a.split("/")[0] for a in args.ipv6_addresses]:
                    upper.address = mac_addr
            if len(added_devices) >= len(args.peer_addresses) and upper.address:
                break
            await asyncio.sleep(5)
        if len(added_devices) < len(args.peer_addresses):
            raise AssertionError("Not all peers added to rules")
        if args.verbose:
            rule_manager.Print()
        prot.set_rulemanager(rule_manager)

        north_task = asyncio.create_task(upper.handle_north())
        south_task = asyncio.create_task(lower.handle_south())
        await asyncio.gather(north_task, south_task)


if __name__ == "__main__":
    asyncio.run(main())
