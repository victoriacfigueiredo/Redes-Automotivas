# -*- coding: utf-8 -*-
import can, time, datetime as dt, logging, pathlib, re

SOURCE_FILE = "benigno.txt"                         # log de origem
logging.basicConfig(
    filename=f"bus(replay)-{dt.datetime.now():%Y%m%d-%H%M%S}.log",
    level=logging.INFO, format='%(message)s')

# (2025-08-07 20:50:54.365804)  can0  098   [1]  01
LINE_RE = re.compile(
    r"\((?P<ts>[0-9\-:.\s]+)\)\s+"
    r"(?P<chan>\w+)\s+"
    r"(?P<id>[0-9A-Fa-f]+)\s+\[(?P<dlc>\d+)\]\s+"
    r"(?P<data>(?:[0-9A-Fa-f]{2}\s*)+)"
)

def parse_line(line: str):
    m = LINE_RE.match(line)
    if not m:
        return None
    # converte timestamp legível ? epoch.float
    ts_str = m.group("ts")
    ts_dt  = dt.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
    ts     = ts_dt.timestamp()

    chan    = m.group("chan")
    arb_id  = int(m.group("id"), 16)
    dlc     = int(m.group("dlc"))
    datahex = m.group("data").strip().split()[:dlc]
    data    = bytes(int(b, 16) for b in datahex)
    return ts, chan, arb_id, data

frames = []
with pathlib.Path(SOURCE_FILE).open() as f:
    for raw in f:
        raw = raw.strip()
        p = parse_line(raw)
        if p:
            frames.append(p)

if not frames:
    raise SystemExit("Nenhum quadro valido encontrado.")

# normaliza tempo relativo
t0 = frames[0][0]
frames = [(ts - t0, chan, arb_id, data) for ts, chan, arb_id, data in frames]

bus = can.interface.Bus('can0', bustype='socketcan')

start = time.time()
for rel_ts, chan, arb_id, data in frames:
    while time.time() - start < rel_ts:
        time.sleep(0.0001)

    msg = can.Message(arbitration_id=arb_id, data=data, is_extended_id=False)
    bus.send(msg)

    data_hex = " ".join(f"{b:02X}" for b in data)
    now = time.time()
    logging.info(f'({now}) {chan} {arb_id:03X}   [{len(data)}]  {data_hex}')
