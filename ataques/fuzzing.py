import can, time, random, datetime, logging

logging.basicConfig(
    filename=f"bus(fuzz)-{datetime.datetime.now():%Y%m%d-%H%M%S}.log",
    level=logging.INFO, format='%(message)s')

def log_line(msg):
    payload = ''.join(f'{b:02X}' for b in msg.data)
    logging.info(f'({msg.timestamp}) {msg.channel} {hex(msg.arbitration_id)}#{payload}')

bus = can.interface.Bus('can0', bustype='socketcan')

try:
    while True:
        arb_id = random.randint(0x500, 0x5FF)
        data   = [random.randint(0,255) for _ in range(8)]
        msg    = can.Message(arbitration_id=arb_id, data=data, is_extended_id=False)
        bus.send(msg)
        log_line(msg)
        time.sleep(0.01)    # 100 msgs/s
except KeyboardInterrupt:
    pass