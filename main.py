import requests, base64, time, threading, sys


def encode_vlq(number: int) -> str:
    bits = f"{number:b}"[::-1]
    bits = [bits[i:i+7] for i in range(0, len(bits), 7)]
    bits = ' '.join([i+"1" for i in bits[:-1]] + [bits[-1]])[::-1]
    hex_res = ""
    for byte in bits.split()[::-1]:
        hex_res += f'{int(byte, 2):02x} '
    return hex_res[:-1]


def decode_vlq(hex_bytes: str) -> int:
    bits = ""
    for byte in hex_bytes.split()[::-1]:
        bits += f'{int(byte, 16):b} '
    bits = bits[::-1].split()
    bits = ''.join([el[:-1] for el in bits[:-1]] + [bits[-1]])[::-1]
    return int(bits, 2)


def compute_crc8(payload: list[str]) -> str:
    pl_int = map(lambda x: int(x, 16), payload)
    generator = 0x1D
    crc = 0
    for byte in pl_int:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80 != 0:
                crc = ((crc << 1) & 0xFF) ^ generator
            else:
                crc = (crc << 1) & 0xFF
    return f"{crc:02x}"


def convert_bytes_to_message(bytes_str: str) -> str:
    return (base64.urlsafe_b64encode(bytes.fromhex(bytes_str))
           .decode("ascii")
           .strip("="))


def convert_response_to_bytes(response_text: str) -> str:
    return bytes.hex(
        base64.urlsafe_b64decode(
        response_text + "====="), " ")


def send_request(func) -> None:
    def wrapper(*args):
        get = func(*args)
        string_to_send = convert_bytes_to_message(get)
        res = requests.post(url, data=string_to_send)
        global my_serial
        my_serial += 1
        global code
        code = res.status_code 
        gotten_bytes = convert_response_to_bytes(res.text)
        parse_response(gotten_bytes)
    return wrapper


def find_dev_by_name(dev_name: str) -> str:
    for dev in devs:
        if devs[dev]["dev_name"] == dev_name:
            return dev


def get_length_crc8(struct: list[str]) -> tuple[str]:
    payload = " ".join(struct[1:-1]).split()
    length = encode_vlq(len(payload))
    crc8 = compute_crc8(payload)
    return length, crc8


@send_request
def whoishere() -> str:
    struct = [None,                        # length
              my_address,                  # src
              broadcast_address,           # dst
              encode_vlq(my_serial),       # serial
              my_dev_type,                 # dev_type
              cmds["whoishere"],           # cmd
              my_dev_name,                 # dev_name
              None                         # crc8
              ]
    
    struct[0], struct[-1] = get_length_crc8(struct)
    return " ".join(struct)


@send_request
def iamhere() -> str:
    struct = [None,                        # length
              my_address,                  # src
              broadcast_address,           # dst
              encode_vlq(my_serial),       # serial
              dev_types["SmartHub"],       # dev_type
              cmds["iamhere"],             # cmd
              my_dev_name,                 # dev_name
              None                         # crc8
              ]

    struct[0], struct[-1] = get_length_crc8(struct)
    return " ".join(struct)


@send_request
def getstatus(dst: str) -> str:
    struct = [None,                        # length
              my_address,                  # src
              dst,                         # dst
              encode_vlq(my_serial),       # serial
              devs[dst]["dev_type"],       # dev_type
              cmds["getstatus"],           # cmd
              None                         # crc8
              ]
    
    struct[0], struct[-1] = get_length_crc8(struct)
    return " ".join(struct)


@send_request
def setstatus(dev_name: str, status: int) -> str:
    dst = find_dev_by_name(dev_name)

    struct = [None,                     # length
              my_address,               # src
              dst,                      # dst
              encode_vlq(my_serial),    # serial
              devs[dst]["dev_type"],    # dev_type
              cmds["setstatus"],        # cmd
              f'{status:02x}',          # status
              None                      # crc8
              ]
    
    struct[0], struct[-1] = get_length_crc8(struct)
    return " ".join(struct)


def parse_response(gotten_bytes: str) -> None:
    gotten_bytes = gotten_bytes.split()

    while len(gotten_bytes) > 0:
        pl_length = int(gotten_bytes[0], 16)
        payload, gotten_bytes = gotten_bytes[1:pl_length+2], gotten_bytes[pl_length+2:]

        # crc8 verification
        if payload.pop() != compute_crc8(payload):
            continue
        
        # src, dst, serial getting
        if "ff" in payload[1:3]:
            dst_idx = payload.index("ff", 1, 3)
            src = " ".join(payload[:dst_idx])
            dst_len = 2
            if src in devs: # STATUS и адрес хаба начинается с "ff" или TICK
                devs[src]["serial"] += 1
            else:
                devs[src] = {}
                devs[src]["serial"] = 1
        else: # STATUS
            dst_len = len(my_address.split())
            dst_idx = payload.index(my_address.split()[0], 1, 3)
            src = " ".join(payload[:dst_idx])
            devs[src]["serial"] += 1
        serial_len = len(encode_vlq(devs[src]["serial"]).split())
        payload = payload[dst_idx+dst_len+serial_len:]
        
        # dev_type getting
        dev_type = payload.pop(0)
        if "dev_type" not in devs[src]:
            devs[src]["dev_type"] = dev_type

        # cmd getting and processing
        cmd = payload.pop(0)
        if cmd == cmds["tick"]:
            global system_time
            system_time = decode_vlq(' '.join(payload))
            continue
        
        elif cmd in (cmds["iamhere"],
                     cmds["whoishere"]):
            if dev_type == dev_types["EnvSensor"]:
                dev_name_len = int(payload.pop(0), 16)
                devs[src]["dev_name"] = str(bytes.fromhex("".join(payload[:dev_name_len])))[2:-1]
                payload = payload[dev_name_len:]

                sensors = f'{int(payload.pop(0), 16):04b}'[::-1]
                sens_types = []
                for i in range(len(sensors)):
                    if int(sensors[i]):
                        sens_types.append(i)
                devs[src]["sens_types"] = sens_types
                temp = str(bytes.fromhex("".join(payload[1:])))[2:-1]
                names = []
                for i in temp.split("\\x"):
                    if len(i) > 4:
                        names.append(i)
                triggers = []
                for name in names:
                    trigger = temp.split("\\x" + name)
                    triggers.append(trigger[0])
                    temp = trigger[1]
                for i in range(len(triggers)):
                    triggers[i] = bytes.hex(eval("b\'" + triggers[i] + "\'"), " ")
                names = list(map(lambda name: name[2:], names))
                devs[src]["triggers"] = {}
                for trigger, name in zip(triggers, names):
                    devs[src]["triggers"][name] = {}
                    op, value = trigger[:2], trigger[3:]
                    op = f'{int(op, 16):04b}'[::-1]
                    devs[src]["triggers"][name]["turn_on"] = int(op[0], 2)
                    devs[src]["triggers"][name]["if_more"] = int(op[1], 2)
                    devs[src]["triggers"][name]["sens_type"] = int(op[:-3:-1], 2)
                    devs[src]["triggers"][name]["value"] = decode_vlq(value)

            elif dev_type == dev_types["Switch"]:
                temp = str(bytes.fromhex("".join(payload)))[6:-1].split("\\x")
                devs[src]["dev_name"], _, *rest = temp
                devs[src]["dev_names"] = list(map(lambda el: el[2:], rest))

            elif dev_type in (dev_types["Lamp"],  # можно else, но для наглядности так лучше
                              dev_types["Switch"],
                              dev_types["Socket"],
                              dev_types["Clock"]):
                devs[src]["dev_name"] = str(bytes.fromhex("".join(payload)))[6:-1]
            if cmd == cmds["whoishere"]:
                next_cmds[cmds["iamhere"]].append(src)

        elif cmd == cmds["status"]:
            if dev_type == dev_types["EnvSensor"]:
                del payload[0]
                for sens_type in devs[src]["sens_types"]:
                    for name in devs[src]["triggers"]:
                        if sens_type == devs[src]["triggers"][name]["sens_type"]:
                            value_len = len(encode_vlq(devs[src]["triggers"][name]["value"]).split())
                            gotten_value, payload = payload[:value_len], payload[value_len:]
                            gotten_value = decode_vlq(" ".join(gotten_value))

                            if ((gotten_value > devs[src]["triggers"][name]["value"] and
                                devs[src]["triggers"][name]["if_more"]) or
                                (gotten_value < devs[src]["triggers"][name]["value"] and
                                not devs[src]["triggers"][name]["if_more"])):

                                next_cmds["05"].append([name, devs[src]["triggers"][name]["turn_on"]])

            elif dev_type in (dev_types["Lamp"],
                              dev_types["Switch"],
                              dev_types["Socket"]):
                devs[src]["status"] = int(payload[0])


def print_devs_content() -> None:
    for dev, content in devs.items():
        print(dev, content)
    print(system_time)
    print()

if __name__ == "__main__":

    url = sys.argv[1] # 'http://127.0.0.1:9998'

    system_time = 0
    code = 200
    devs = {}

    broadcast_address = "ff 7f"
    my_address = encode_vlq(int(sys.argv[2], 16)) # ef0
    my_serial = 1
    my_dev_type = "01"
    my_dev_name = "05 48 55 42 30 31" # bytes.hex("HUB01".encode('ascii'), sep=' ')

    cmds = {
        "whoishere": "01",
        "iamhere": "02",
        "getstatus": "03",
        "status": "04",
        "setstatus": "05",
        "tick": "06"
    }
    dev_types = {
        "SmartHub": "01",
        "EnvSensor": "02",
        "Switch": "03",
        "Lamp": "04",
        "Socket": "05",
        "Clock": "06"
    }
    next_cmds = {"02": [], "05": []} # IAMHERE, SETSTATUS
    wait_for_response = {}


    def program():
        while True:
            try:
                getstatus(clock)
                while len(next_cmds["02"]) > 0:
                    iamhere()
                    del next_cmds["02"][0]
                if len(next_cmds["05"]) > 0:
                    for el in next_cmds["05"]:
                        name, status = el
                        setstatus(*el)
                        addr = find_dev_by_name(name)
                        wait_for_response[addr] = [system_time + 300, status]
                    next_cmds["05"].clear
                if len(wait_for_response) > 0:
                    for dev in range(len(wait_for_response.copy())):
                        if system_time > wait_for_response[dev][0]:
                            if devs[dev]["status"] != wait_for_response[dev][1]:
                                del devs[dev]
                            del wait_for_response[dev]
                if code == 204:
                    sys.exit(0)
                elif code not in (200, 204):
                    sys.exit(99)
                time.sleep(0.1)
            except:
                sys.exit(99)
        

    whoishere()
    for dev in devs:
        if devs[dev]['dev_type'] == dev_types["Clock"]:
            clock = dev
    getstatus(clock)
    for dev in devs:
            getstatus(dev)

    threading.Thread(target=program).start()
