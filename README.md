# Wireless Performance Analysis

Laboratory project evaluating TCP and UDP goodput across Ethernet-to-Ethernet, Ethernet-to-WiFi, and WiFi-to-WiFi topologies using the IEEE 802.11b and 802.11g standards.

Authors: Michele Cetraro, Lorenzo Giandomenico, Christian Lombardozzi, and Alessandro Minutoli.

## Files

- [wireless_performance.pdf](wireless_performance.pdf): compiled project report.
- [script.py](script.py): automated iperf3 measurements and statistical summaries.

## Requirements

Python 3.9 or later on the client and iperf3 on both hosts. The script uses only the Python standard library. TCP interface MTU sweeps require Linux, iproute2, and root privileges.

On Ubuntu:

```bash
sudo apt install iperf3 iproute2
```

## Usage

Start iperf3 on the server:

```bash
iperf3 -s
```

Run the following commands on the client, replacing the IP address and interface name with those of your testbed.

### UDP

```bash
python3 script.py --server 192.168.1.2 --protocol udp \
  --scenario eth-wifi-g-baseline --reverse --bitrate 100M \
  --sizes 64 128 256 512 1024 1400 1472 1500 \
  --duration 10 --repetitions 10
```

`--sizes` specifies the UDP payload in bytes. `--bitrate` sets the offered load: 100M is an example intended to saturate the link and should be adjusted for each experiment. With IPv4 without options and a path MTU of 1500 bytes, the maximum payload without fragmentation is 1472 bytes. The 1500-byte case can be used to study fragmentation effects if the path permits fragmentation.

### TCP

```bash
sudo python3 script.py --server 192.168.1.2 --protocol tcp \
  --scenario eth-wifi-g-baseline --interface wlan0 --reverse \
  --sizes 128 256 512 768 1024 1500 \
  --duration 10 --repetitions 10
```

For TCP, `--sizes` specifies the local interface MTU, not the application payload. The script records the initial MTU and attempts to restore it on exit, including when interrupted with Ctrl+C. Forced termination or a system shutdown may prevent restoration.

`--reverse` sends traffic from the server to the client; without this option, traffic flows from the client to the server. Configure the WiFi standard, channel, Ethernet link speed, RTS/CTS, and interference conditions separately on the testbed.

Preview the commands without generating traffic or changing the MTU:

```bash
python3 script.py --server 192.168.1.2 --protocol tcp \
  --scenario preview --interface wlan0 --dry-run
```

## Results

Each execution creates a separate directory under `results/`, containing:

- `metadata.json`: parameters, iperf3 version, and initial MTU when applicable.
- `.stdout.json` and `.stderr.txt` files: raw output from each completed process.
- `measurements.csv`: receiver goodput in Mbit/s, packet loss and jitter when available, status, and any error.
- `summary.csv`: mean, minimum, maximum, sample standard deviation, and counts of successful and failed trials for each size.

Failed trials are excluded from the statistics rather than treated as zero goodput. The standard deviation field is left empty when fewer than two successful measurements are available.

The included script is a new implementation supporting the project, not the original script used to obtain the measurements in the report. It has not been validated on the original testbed.
