# Wireless Performance Analysis

Progetto di laboratorio per valutare il goodput TCP e UDP nelle topologie Ethernet-Ethernet, Ethernet-WiFi e WiFi-WiFi, con standard IEEE 802.11b e 802.11g.

Autori: Michele Cetraro, Lorenzo Giandomenico, Christian Lombardozzi e Alessandro Minutoli.

## File

- [Wifi_lab.pdf](Wifi_lab.pdf): relazione compilata del progetto.
- [script.py](script.py): automazione delle misure con iperf3 e riepilogo statistico.

## Requisiti

Python 3.9 o successivo e iperf3 su entrambi gli host. Lo script usa solo la libreria standard Python. Per la variazione della MTU TCP servono Linux, iproute2 e privilegi root.

Su Ubuntu:

```bash
sudo apt install iperf3 iproute2
```

## Utilizzo

Avviare sul server:

```bash
iperf3 -s
```

Sul client, sostituire l'indirizzo IP e il nome dell'interfaccia con quelli del proprio testbed.

### UDP

```bash
python3 script.py --server 192.168.1.2 --protocol udp \
  --scenario eth-wifi-g-baseline --reverse --bitrate 100M \
  --sizes 64 128 256 512 1024 1400 1472 1500 \
  --duration 10 --repetitions 10
```

`--sizes` indica il payload UDP in byte. `--bitrate` specifica il carico offerto: 100M è un esempio di saturazione, da adattare all'esperimento. Con IPv4 senza opzioni e MTU di percorso 1500, il limite senza frammentazione è 1472 byte; il caso 1500 permette di studiarne gli effetti, se il percorso consente la frammentazione.

### TCP

```bash
sudo python3 script.py --server 192.168.1.2 --protocol tcp \
  --scenario eth-wifi-g-baseline --interface wlan0 --reverse \
  --sizes 128 256 512 768 1024 1500 \
  --duration 10 --repetitions 10
```

Per TCP, `--sizes` indica la MTU dell'interfaccia locale, non il payload applicativo. Lo script registra la MTU iniziale e tenta di ripristinarla al termine, anche su Ctrl+C. Un arresto forzato o uno spegnimento può impedire il ripristino.

`--reverse` invia dal server al client; senza questa opzione il traffico va dal client al server. Standard WiFi, canale, velocità Ethernet, RTS/CTS e condizioni di interferenza vanno configurati separatamente sul testbed.

Anteprima dei comandi senza generare traffico o modificare la MTU:

```bash
python3 script.py --server 192.168.1.2 --protocol tcp \
  --scenario preview --interface wlan0 --dry-run
```

## Risultati

Ogni esecuzione crea una cartella distinta sotto `results/`, contenente:

- `metadata.json`: parametri, versione iperf3 e MTU iniziale quando applicabile.
- File `.stdout.json` e `.stderr.txt`: output originale di ogni processo concluso.
- `measurements.csv`: goodput al ricevitore in Mbit/s, perdita e jitter se disponibili, stato ed eventuale errore.
- `summary.csv`: media, minimo, massimo, deviazione standard campionaria e numero di prove riuscite o fallite per dimensione.

Le prove fallite sono escluse dalle statistiche e non vengono interpretate come goodput zero. Il valore della deviazione standard è vuoto quando sono disponibili meno di due misure riuscite.

Lo script incluso è una nuova implementazione di supporto al progetto, non lo script originale con cui sono state ottenute le misure della relazione; non è stato validato sul testbed originale.
