#!/usr/bin/env python3
"""Run IPv4 iperf3 sweeps; save receiver goodput and every raw result."""
import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone


def receiver_metrics(result, protocol):
    if result.get('error'):
        raise ValueError(result['error'])
    end = result['end']
    record = end.get('sum_received')
    if record is None and protocol == 'udp':
        candidates = [s['udp'] for s in end.get('streams', [])
                      if 'udp' in s and s['udp'].get('sender') is False]
        record = candidates[0] if len(candidates) == 1 else None
        if record is None and end.get('sum', {}).get('sender') is False:
            record = end['sum']
    if record is None:
        raise ValueError('Receiver statistics missing; refusing sender-rate fallback')
    return {'goodput_mbps': float(record['bits_per_second']) / 1e6,
            'lost_percent': record.get('lost_percent', ''),
            'jitter_ms': record.get('jitter_ms', '')}


def summarize(rows):
    output = []
    for size in sorted({r['size_bytes'] for r in rows}):
        group = [r for r in rows if r['size_bytes'] == size]
        values = [r['goodput_mbps'] for r in group if r['status'] == 'ok']
        output.append(dict(size_bytes=size, successful=len(values), failed=len(group)-len(values),
                           mean_mbps=statistics.mean(values) if values else '',
                           min_mbps=min(values) if values else '',
                           max_mbps=max(values) if values else '',
                           stdev_mbps=statistics.stdev(values) if len(values)>1 else ''))
    return output


def write_csv(path, rows):
    if rows:
        with path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True)
    parser.add_argument('--protocol', choices=['tcp', 'udp'], required=True)
    parser.add_argument('--scenario', required=True, help='Descriptive label, e.g. eth-wifi-g-baseline')
    parser.add_argument('--sizes', type=int, nargs='+', help='UDP payloads or TCP interface MTUs in bytes')
    parser.add_argument('--interface', help='Linux client interface, required for TCP MTU sweep')
    parser.add_argument('--bitrate', help='UDP offered load, e.g. 100M; required for UDP')
    parser.add_argument('--reverse', action='store_true', help='Send server -> client')
    parser.add_argument('--duration', type=int, default=10)
    parser.add_argument('--repetitions', type=int, default=10)
    parser.add_argument('--pause', type=float, default=1)
    parser.add_argument('--port', type=int, default=5201)
    parser.add_argument('--output', type=Path, default=Path('results'))
    parser.add_argument('--dry-run', action='store_true', help='Print commands without network or MTU changes')
    args = parser.parse_args(argv)
    if args.duration <= 0 or args.repetitions <= 0 or args.pause < 0 or not 1 <= args.port <= 65535:
        parser.error('Invalid duration, repetitions, pause or port')
    sizes = args.sizes or ([64,128,256,512,1024,1400,1472,1500] if args.protocol=='udp'
                           else [128,256,512,768,1024,1500])
    if any(s <= 0 or s > (65507 if args.protocol=='udp' else 65535) for s in sizes):
        parser.error('Invalid size')
    if args.protocol=='udp' and not args.bitrate:
        parser.error('--bitrate is required for UDP (explicit offered load)')
    if args.protocol=='tcp' and (not args.interface or min(sizes)<68):
        parser.error('TCP requires --interface and IPv4 MTUs >= 68')
    if args.protocol=='tcp' and not args.dry_run:
        if not sys.platform.startswith('linux') or os.geteuid()!=0:
            parser.error('TCP MTU sweep requires Linux and root privileges')
        if not shutil.which('ip'):
            parser.error('iproute2 is required')
    if not args.dry_run and not shutil.which('iperf3'):
        parser.error('iperf3 is not installed')
    commands = []
    for size in sizes:
        cmd = ['iperf3','-4','-c',args.server,'-p',str(args.port),'-t',str(args.duration),
               '-J','--get-server-output']
        if args.reverse:
            cmd += ['-R']
        if args.protocol=='udp':
            cmd += ['-u','-b',args.bitrate,'-l',str(size)]
        commands.append((size, cmd))
    if args.dry_run:
        for size, cmd in commands:
            if args.protocol=='tcp':
                print(f'MTU {args.interface}: {size} bytes (restore original after sweep)')
            print(' '.join(cmd), f'[{args.repetitions} repetitions]')
        return 0
    # A unique directory prevents accidental replacement of previous measurements.
    run_dir = args.output / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    run_dir.mkdir(parents=True, exist_ok=False)
    original_mtu = None
    if args.protocol=='tcp':
        info = json.loads(subprocess.check_output(['ip','-j','link','show','dev',args.interface], text=True))
        original_mtu = int(info[0]['mtu'])
    metadata = vars(args).copy()
    metadata.update(output=str(args.output), sizes=sizes, original_mtu=original_mtu,
                    size_kind='udp_payload' if args.protocol=='udp' else 'client_interface_mtu',
                    iperf_version=subprocess.check_output(['iperf3','--version'],text=True),
                    started_utc=datetime.now(timezone.utc).isoformat())
    (run_dir/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    rows = []
    try:
        for size, cmd in commands:
            if original_mtu is not None:
                subprocess.run(['ip','link','set','dev',args.interface,'mtu',str(size)],check=True)
            for repetition in range(1,args.repetitions+1):
                row = dict(size_bytes=size,repetition=repetition,status='error',
                           goodput_mbps='',lost_percent='',jitter_ms='',error='')
                stem = run_dir/f'{size}_{repetition:02d}'
                try:
                    process = subprocess.run(cmd,capture_output=True,text=True,timeout=args.duration+30)
                    stem.with_suffix('.stdout.json').write_text(process.stdout,encoding='utf-8')
                    stem.with_suffix('.stderr.txt').write_text(process.stderr,encoding='utf-8')
                    if process.returncode:
                        raise ValueError(f'iperf3 exit {process.returncode}: {process.stderr.strip()} {process.stdout[:300]}')
                    row.update(receiver_metrics(json.loads(process.stdout),args.protocol),status='ok')
                except (ValueError,KeyError,TypeError,OSError,subprocess.TimeoutExpired) as exc:
                    row['error'] = str(exc)
                rows.append(row)
                write_csv(run_dir/'measurements.csv',rows)
                write_csv(run_dir/'summary.csv',summarize(rows))
                print(f'{size} bytes, run {repetition}: {row["status"]} {row["goodput_mbps"]}',flush=True)
                time.sleep(args.pause)
    finally:
        if original_mtu is not None:
            subprocess.run(['ip','link','set','dev',args.interface,'mtu',str(original_mtu)],check=True)
    print(f'Results: {run_dir}')
    return 1 if any(r['status']!='ok' for r in rows) else 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('Interrupted; partial results saved and MTU restoration attempted.',file=sys.stderr)
        raise SystemExit(130)
