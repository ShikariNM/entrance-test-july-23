### Introduction
The program was made as an entrance test for an educational program in one of Russian companies. Applicants were given 4 days to implement the program. The program has not been edited since it was done after the lapse of the 4 days to leave it in original state. Some of the task requirements were omitted in the README eather accidentally or deliberately, because the README is inteded to provide a general idea of the task. It should be mentioned, that the task had some omissions: some details were not specified, that caused difficulties during task implementation. For instance, Switch does not process command SETSTATUS, so the program has to appeal to connected devices directly, nevertheless the task claims, that "Switch status alternation must set the statuses of all connected devices in the same state as switch has". Thus, the program does not have instrument to affect switch status, but somehow it must affect.

### Essence
The program was intended to be a part of a Hub in a smart home system and used to control system device functioning.

### Devices
Each device has a unique identification number (from 1 to 16382, 16383 - broadcast address, varint), a unique name (string), device type number (byte), counts the amount of sent packets (varint).

The system consists of 6 types of devices:
1. __HUB__ (only one instance in the system)
* controls system devices
2. __ENVIRONMENT SENSOR (ENVSENS)__
* measures environment parameters and sends the notification, that some parameter is out of normal range, to the HUB
* keeps information about:
    * the types of parameters being measured (byte, maximum - 4 types, looks like 4 bits, each bit indicates the presence of a specific sensor, the sensor number is the bit's index)
    * settings for each parameter (which state (bit, on/off) must have the respective device (name), when parameter crosses (bit, more/less) set value (varint))
3. __SWITCH__ - intermediate link between the HUB and various combinations of LAMPs and SOCKETs.
* keeps information about self state (bit, on/off) and connected devices (name).
4. __LAMP__
* keeps information about self state (bit, on/off)
5. __SOCKET__
* keeps information about self state (bit, on/off)
6. __CLOCK__ (only one instance in the system)
* informs about the time in the system

### Communication
All system devices communicate sending broadcast packets or direct packets to the HUB. Packets are base64 encoded binary form JSON-object, which means JSON-object is converted in binary form and then base64 encoded. Each JSON-object consists of payload length (byte) at the beginning of the message, payload itself, and payload control sum (byte, crc8 algorithm is used to count) at the end of the message. Control sum must be verified when HUB receives the message. In case it does not correspond to computed value, packet is skipped. The only way of HUB communication with the system is HTTP post request.

All communication comprises 6 commands:
1. __WHOISHERE__ - a broadcast command.
* is sent by each device arisen in the system
* contains information about sending device
* the HUB sends it once, when the program starts, to gather information about the connected devices;
* each device, gotten WHOISHERE, must respond with IAMHERE command;
* SWITCH, LAMP and SOCKET do not send self status in this command;
2. __IAMHERE__ - a broadcast command.
* is sent as a response to WHOISHERE;
* contains information about sending device;
* SWITCH, LAMP and SOCKET do not send self status in this command;
3. __GETSTATUS__ - specific HUB command.
* is used to get information about the status of devices in the system, after sending WHOISHERE command
* is addressed directly to each device
* devices respond with STATUS command

4. __STATUS__ - ENVSENS, SWITCH, LAMP and SOCKET command.
* ENVSENS sends current values for each embedded sensor
* if any sensor of ENVSES is triggered, ENVSENS sends this command itself
* SWITCH, LAMP and SOCKET send self status

5. __SETSTATUS__ - specific HUB command.
* is used to change a state of respective device in case of reception of STATUS command from ENVSENS.
* recipient must respond with STATUS command during next 300 ms, otherwise the device is considered to be excluded from the system.

6. __TICK__ - specific broadcast CLOCK command.
* is sent by CLOCK periodically (~ every 100ms) to inform devices about the system time.

### Command examples
![WHOISHERE by HUB](/images/WHOISHERE_by_HUB.png "WHOISHERE by HUB")
![IAMHERE by ENVSENS](/images/IAMHERE_by_ENVSENS.png "IAMHERE by ENVSENS")
![IAMHERE by SWITCH](/images/IAMHERE_by_SWITCH.png "IAMHERE by SWITCH")
![GETSTATUS from HUB to ENVSENS](/images/GETSTATUS_from_HUB_to_ENVSENS.png "GETSTATUS from HUB to ENVSENS")
![STATUS by ENVSENS](/images/STATUS_by_ENVSENS.png "STATUS by ENVSENS")
![SETSTATUS from HUB to LAMP](/images/SETSTATUS_from_HUB_to_LAMP.png "SETSTATUS from HUB to LAMP")
![TICK by CLOCK](/images/TICK_by_CLOCK.png "TICK by CLOCK")