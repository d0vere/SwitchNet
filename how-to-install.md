# SwitchNet — Guida completa a compilazione e flash

Questa guida descrive passo per passo come preparare l'ambiente, compilare e flashare **SwitchNet** su una board **ESP32-S3 con USB nativa**, sia su **Windows** sia su **Linux**.

Repository del progetto:

```text
https://github.com/d0vere/SwitchNet
```

> [!IMPORTANT]
> SwitchNet richiede un **ESP32-S3 con supporto USB nativo** e deve essere compilato usando la modalità USB compatibile con **USB-OTG / TinyUSB**.
>
> Il progetto utilizza inoltre una `partitions.csv` personalizzata. Per il primo passaggio a questo layout di flash è raccomandato un **flash completo via USB**, non un aggiornamento OTA del solo firmware.

---

## Indice

1. [Hardware necessario](#1-hardware-necessario)
2. [Architettura di SwitchNet](#2-architettura-di-switchnet)
3. [Scaricare il repository](#3-scaricare-il-repository)
4. [Installare Arduino CLI](#4-installare-arduino-cli)
5. [Configurare Arduino CLI](#5-configurare-arduino-cli)
6. [Installare il core ESP32](#6-installare-il-core-esp32)
7. [Collegare e identificare la board](#7-collegare-e-identificare-la-board)
8. [Permessi seriali su Linux](#8-permessi-seriali-su-linux)
9. [Configurazione ESP32-S3](#9-configurazione-esp32-s3)
10. [Verificare le opzioni USB](#10-verificare-le-opzioni-usb)
11. [Compilare SwitchNet](#11-compilare-switchnet)
12. [Flash su Windows](#12-flash-su-windows)
13. [Flash su Linux](#13-flash-su-linux)
14. [Entrare manualmente nel bootloader](#14-entrare-manualmente-nel-bootloader)
15. [Verificare il flash delle partizioni](#15-verificare-il-flash-delle-partizioni)
16. [Monitor seriale](#16-monitor-seriale)
17. [Primo avvio](#17-primo-avvio)
18. [Collegamento alla Nintendo Switch](#18-collegamento-alla-nintendo-switch)
19. [Troubleshooting](#19-troubleshooting)
20. [Cancellare completamente la flash](#20-cancellare-completamente-la-flash)
21. [Procedura rapida Windows](#21-procedura-rapida-windows)
22. [Procedura rapida Linux](#22-procedura-rapida-linux)
23. [Checklist finale](#23-checklist-finale)

---

# 1. Hardware necessario

Per seguire questa guida servono:

- una board **ESP32-S3 con USB nativa**;
- preferibilmente **4 MB di flash** se si utilizza il layout `partitions.csv` fornito dal progetto;
- un cavo USB che supporti **trasferimento dati**, non solo alimentazione;
- un PC Windows oppure Linux;
- una Nintendo Switch / Switch OLED / Switch 2 compatibile con il comportamento previsto dal progetto;
- una connessione di rete tra il PC che esegue il client SwitchNet e l'ESP32-S3.

Una board come la Waveshare basata su **ESP32-S3FH4R2** dispone di:

- ESP32-S3 dual-core;
- 4 MB di flash;
- 2 MB di PSRAM;
- Wi-Fi 2.4 GHz;
- supporto USB nativo a livello di SoC.

La caratteristica più importante per SwitchNet è la disponibilità della **USB nativa dell'ESP32-S3**, perché il firmware deve presentarsi alla console come dispositivo USB HID.

---

# 2. Architettura di SwitchNet

Il flusso generale è:

```text
Controller / tastiera / mouse
            │
            ▼
           PC
            │
       LAN / Wi-Fi
            │
            ▼
        ESP32-S3
            │
       USB nativa
            │
            ▼
     Nintendo Switch
```

L'ESP32-S3 riceve gli input tramite rete e utilizza la USB nativa per presentarsi come controller.

Per questo motivo una semplice ESP32 con UART USB o un bridge CH340/CP210x non è sufficiente: è necessario che il microcontrollore possa gestire direttamente il device USB.

---

# 3. Scaricare il repository

## Windows

Installare Git per Windows se non è già presente, quindi aprire **PowerShell**:

```powershell
cd $HOME
git clone https://github.com/d0vere/SwitchNet.git
cd SwitchNet
```

Verificare il contenuto:

```powershell
dir
```

Dovrebbero essere presenti almeno:

```text
SwitchNet.ino
partitions.csv
src
```

## Linux

Aprire un terminale:

```bash
cd ~
git clone https://github.com/d0vere/SwitchNet.git
cd SwitchNet
```

Verificare:

```bash
ls
```

Dovrebbero essere presenti almeno:

```text
SwitchNet.ino
partitions.csv
src/
```

> [!WARNING]
> Non copiare solamente `SwitchNet.ino` in un'altra cartella.
>
> Il progetto dipende dai sorgenti presenti in `src/` e dalla tabella partizioni `partitions.csv`.

---

# 4. Installare Arduino CLI

SwitchNet può essere compilato comodamente tramite **Arduino CLI**.

---

## 4.1 Windows

Scaricare Arduino CLI dal sito ufficiale Arduino e installare `arduino-cli.exe` in una directory presente nel `PATH`.

Dopo l'installazione aprire un nuovo PowerShell e verificare:

```powershell
arduino-cli version
```

Se PowerShell restituisce:

```text
arduino-cli : The term 'arduino-cli' is not recognized
```

significa che la cartella contenente `arduino-cli.exe` non è stata aggiunta correttamente alla variabile `PATH`.

### Alternativa con Git Bash

Se Git Bash è installato:

```bash
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
```

In questo caso lo script crea normalmente un eseguibile sotto una directory `bin`.

---

## 4.2 Linux

Installare prima Git e curl.

Debian / Ubuntu:

```bash
sudo apt update
sudo apt install -y git curl
```

Installare Arduino CLI:

```bash
cd ~
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
```

Lo script può creare:

```text
~/bin/arduino-cli
```

Aggiungere `~/bin` al `PATH`:

```bash
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Verificare:

```bash
arduino-cli version
```

---

# 5. Configurare Arduino CLI

Inizializzare la configurazione:

```bash
arduino-cli config init
```

Se Arduino CLI comunica che il file esiste già, non è un problema.

Visualizzare la configurazione:

```bash
arduino-cli config dump
```

Aggiungere l'indice ufficiale delle board Espressif:

```bash
arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
```

Aggiornare gli indici:

```bash
arduino-cli core update-index
```

Controllare:

```bash
arduino-cli config dump
```

Dovrebbe essere presente qualcosa di simile:

```yaml
board_manager:
  additional_urls:
    - https://espressif.github.io/arduino-esp32/package_esp32_index.json
```

---

# 6. Installare il core ESP32

La procedura descritta in questa guida utilizza:

```text
Arduino-ESP32 3.3.11
```

Installarlo esplicitamente:

```bash
arduino-cli core install esp32:esp32@3.3.11
```

Verificare:

```bash
arduino-cli core list
```

L'output dovrebbe includere:

```text
ID           Installed
esp32:esp32  3.3.11
```

> [!NOTE]
> Usare una versione esplicitamente indicata dal progetto rende la build più riproducibile ed evita differenze nei menu board, nel supporto TinyUSB o nella gestione di `partitions.csv`.

---

# 7. Collegare e identificare la board

Collegare l'ESP32-S3 con un cavo USB dati.

Eseguire:

```bash
arduino-cli board list
```

## Windows

Esempio:

```text
Port  Protocol Type
COM5  serial   Serial Port (USB)
```

In questo esempio la porta da utilizzare è:

```text
COM5
```

## Linux

Esempi comuni:

```text
/dev/ttyACM0
```

oppure:

```text
/dev/ttyUSB0
```

Con USB nativa ESP32-S3 è frequente vedere una porta `/dev/ttyACM*`.

Per confrontare prima e dopo aver collegato la board:

```bash
arduino-cli board list
```

---

# 8. Permessi seriali su Linux

Controllare i permessi:

```bash
ls -l /dev/ttyACM0
```

Se il dispositivo appartiene al gruppo `dialout`, aggiungere l'utente corrente:

```bash
sudo usermod -aG dialout $USER
```

Effettuare logout/login.

Verificare:

```bash
groups
```

Dovrebbe comparire:

```text
dialout
```

Per una sessione temporanea si può anche provare:

```bash
newgrp dialout
```

> [!WARNING]
> Evitare come soluzione permanente:
>
> ```bash
> sudo chmod 777 /dev/ttyACM0
> ```
>
> È una soluzione temporanea e poco corretta dal punto di vista dei permessi.

---

# 9. Configurazione ESP32-S3

Il target Arduino generico normalmente utilizzato per una ESP32-S3 è:

```text
esp32:esp32:esp32s3
```

Verificare che esista.

Linux:

```bash
arduino-cli board listall | grep -i "ESP32-S3"
```

Windows PowerShell:

```powershell
arduino-cli board listall | Select-String "ESP32-S3"
```

Dovrebbe comparire una board simile a:

```text
ESP32S3 Dev Module    esp32:esp32:esp32s3
```

Per una board ESP32-S3 SuperMini o una board generica basata sullo stesso SoC, questo è il punto di partenza abituale.

---

# 10. Verificare le opzioni USB

SwitchNet richiede che la USB nativa venga configurata in una modalità compatibile con **USB-OTG / TinyUSB**.

Visualizzare tutte le opzioni disponibili:

```bash
arduino-cli board details --fqbn esp32:esp32:esp32s3
```

Su Linux è possibile filtrare:

```bash
arduino-cli board details --fqbn esp32:esp32:esp32s3 | grep -i -A12 usb
```

Su Windows PowerShell:

```powershell
arduino-cli board details --fqbn esp32:esp32:esp32s3 | Select-String -Pattern "USB" -Context 0,12
```

Cercare una voce equivalente a:

```text
USB Mode
  USB-OTG (TinyUSB)
```

Il nome interno esatto dell'opzione Arduino CLI va letto dall'output della versione del core installata.

Il formato generale di un FQBN con opzioni è:

```text
esp32:esp32:esp32s3:OPZIONE=VALORE
```

Ad esempio, concettualmente:

```text
esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>
```

> [!IMPORTANT]
> Non copiare alla cieca il valore interno di `USBMode` da tutorial relativi ad altre versioni del core ESP32.
>
> Usare il valore indicato da:
>
> ```bash
> arduino-cli board details --fqbn esp32:esp32:esp32s3
> ```

---

# 11. Compilare SwitchNet

Entrare nella root del progetto.

## Windows

```powershell
cd $HOME\SwitchNet
```

## Linux

```bash
cd ~/SwitchNet
```

Verificare:

```text
SwitchNet.ino
partitions.csv
src/
```

---

## 11.1 Prima compilazione di controllo

Provare:

```bash
arduino-cli compile --fqbn esp32:esp32:esp32s3 .
```

Se SwitchNet segnala che la modalità USB non è corretta, significa che il target ESP32-S3 è stato riconosciuto ma bisogna impostare esplicitamente USB-OTG/TinyUSB.

---

## 11.2 Compilazione con modalità USB corretta

Una volta individuato il valore interno della modalità USB:

### Linux

```bash
arduino-cli compile \
  --fqbn "esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>" \
  .
```

### Windows PowerShell

```powershell
arduino-cli compile --fqbn "esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>" .
```

Una compilazione riuscita termina con informazioni simili a:

```text
Sketch uses XXXXX bytes (...) of program storage space.
Global variables use XXXXX bytes (...) of dynamic memory.
```

---

## 11.3 Directory build separata

È possibile mantenere gli artefatti di compilazione in una directory dedicata.

### Linux

```bash
mkdir -p build
```

```bash
arduino-cli compile \
  --fqbn "esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>" \
  --output-dir build \
  .
```

### Windows

```powershell
mkdir build
```

```powershell
arduino-cli compile --fqbn "esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>" --output-dir build .
```

Tra i file generati possono comparire:

```text
SwitchNet.ino.bin
SwitchNet.ino.bootloader.bin
SwitchNet.ino.partitions.bin
```

I nomi effettivi dipendono dalla versione della toolchain.

---

# 12. Flash su Windows

Identificare la porta:

```powershell
arduino-cli board list
```

Supponiamo sia:

```text
COM5
```

Compilare:

```powershell
arduino-cli compile --fqbn "esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>" .
```

Flashare:

```powershell
arduino-cli upload -v -p COM5 --fqbn "esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>" .
```

È possibile anche compilare e flashare insieme:

```powershell
arduino-cli compile --upload -p COM5 --fqbn "esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>" .
```

Per il primo setup è comunque più semplice tenere separati compile e upload, in modo da capire immediatamente in quale fase si verifica un eventuale errore.

---

# 13. Flash su Linux

Identificare la porta:

```bash
arduino-cli board list
```

Supponiamo:

```text
/dev/ttyACM0
```

Compilare:

```bash
arduino-cli compile \
  --fqbn "esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>" \
  .
```

Flashare:

```bash
arduino-cli upload \
  -v \
  -p /dev/ttyACM0 \
  --fqbn "esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>" \
  .
```

Oppure:

```bash
arduino-cli compile \
  --upload \
  -p /dev/ttyACM0 \
  --fqbn "esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>" \
  .
```

---

# 14. Entrare manualmente nel bootloader

Se Arduino CLI restituisce errori come:

```text
Failed to connect to ESP32-S3
```

oppure:

```text
No serial data received
```

mettere manualmente la board in modalità download.

Una procedura comune sulle board ESP32-S3 con tasti BOOT e RESET è:

1. tenere premuto **BOOT**;
2. premere e rilasciare **RESET/RST**;
3. attendere circa mezzo secondo;
4. rilasciare **BOOT**.

Poi rieseguire:

```bash
arduino-cli board list
```

La porta può cambiare.

Esempio Windows:

```text
COM5 -> COM6
```

Esempio Linux:

```text
/dev/ttyACM0 -> /dev/ttyACM1
```

Usare la nuova porta per il flash.

### Variante

Su alcune board:

1. scollegare USB;
2. tenere premuto BOOT;
3. collegare USB;
4. attendere un secondo;
5. rilasciare BOOT.

Poi controllare nuovamente:

```bash
arduino-cli board list
```

---

# 15. Verificare il flash delle partizioni

SwitchNet utilizza una `partitions.csv` personalizzata.

Per questo motivo il **primo flash** dopo aver adottato questo layout deve essere eseguito via USB in modo che venga scritta anche la partition table.

Usare upload verbose:

### Linux

```bash
arduino-cli upload \
  -v \
  -p /dev/ttyACM0 \
  --fqbn "esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>" \
  .
```

### Windows

```powershell
arduino-cli upload -v -p COM5 --fqbn "esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>" .
```

Nell'output cercare il caricamento del file delle partizioni, normalmente scritto nell'area della partition table.

Il file del progetto:

```text
partitions.csv
```

deve rimanere nella root dello sketch.

> [!IMPORTANT]
> Non flashare solamente `SwitchNet.ino.bin` durante il primo setup.
>
> Il normale comando `arduino-cli upload` è preferibile perché gestisce bootloader, partition table e applicazione secondo la configurazione Arduino.

---

# 16. Monitor seriale

Il monitor seriale è molto utile per controllare l'avvio.

Verificare prima la porta:

```bash
arduino-cli board list
```

### Windows

```powershell
arduino-cli monitor -p COM5 -c baudrate=115200
```

### Linux

```bash
arduino-cli monitor -p /dev/ttyACM0 -c baudrate=115200
```

Se dopo il reset la porta cambia, ripetere:

```bash
arduino-cli board list
```

e utilizzare il nuovo device.

Per uscire dal monitor utilizzare la combinazione mostrata da Arduino CLI all'avvio del monitor.

---

# 17. Primo avvio

Dopo il flash:

1. premere RESET oppure scollegare e ricollegare la board;
2. aprire il monitor seriale;
3. controllare i messaggi di boot;
4. verificare che il firmware SwitchNet venga avviato;
5. completare la configurazione di rete prevista dal progetto.

Se la board era già stata usata precedentemente, nella memoria NVS potrebbero essere presenti configurazioni salvate.

Se il comportamento è anomalo, valutare una cancellazione completa della flash come descritto più avanti.

---

# 18. Collegamento alla Nintendo Switch

Una volta che:

- SwitchNet è correttamente flashato;
- l'ESP32-S3 è configurato in rete;
- il client SwitchNet sul PC è attivo;

collegare la USB nativa della board alla Nintendo Switch o al dock, in base alla configurazione hardware utilizzata.

Sulla console abilitare la comunicazione cablata del Pro Controller:

```text
Impostazioni di sistema
  -> Controller e sensori
  -> Comunicazione via cavo del Pro Controller
```

Il firmware utilizza la USB nativa dell'ESP32-S3 per presentare un dispositivo HID alla console.

---

# 19. Troubleshooting

## 19.1 `arduino-cli` non trovato

Windows:

```text
arduino-cli : The term 'arduino-cli' is not recognized
```

Controllare il `PATH` e riaprire PowerShell.

Linux:

```text
arduino-cli: command not found
```

Provare:

```bash
export PATH="$HOME/bin:$PATH"
```

e verificare:

```bash
arduino-cli version
```

---

## 19.2 Board non rilevata

Eseguire:

```bash
arduino-cli board list
```

Se non compare nulla:

- cambiare cavo USB;
- provare un'altra porta USB;
- evitare hub USB durante il debug;
- provare la modalità BOOT manuale;
- controllare Gestione dispositivi su Windows;
- controllare `dmesg` su Linux.

Linux:

```bash
sudo dmesg | tail -n 50
```

Controllare anche:

```bash
ls /dev/ttyACM*
ls /dev/ttyUSB*
```

---

## 19.3 `Permission denied` su Linux

Esempio:

```text
Permission denied: /dev/ttyACM0
```

Soluzione:

```bash
sudo usermod -aG dialout $USER
```

Effettuare logout/login.

---

## 19.4 Porta COM occupata su Windows

Errori tipici:

```text
Access is denied
```

oppure:

```text
could not open port COM5
```

Chiudere eventuali programmi che stanno usando la porta:

- Arduino Serial Monitor;
- PuTTY;
- VS Code Serial Monitor;
- PlatformIO Monitor;
- altri terminali seriali.

Poi riprovare.

---

## 19.5 `Failed to connect to ESP32-S3`

Mettere manualmente la board in bootloader:

```text
BOOT premuto
-> pressione RESET
-> rilascio RESET
-> rilascio BOOT
```

Poi:

```bash
arduino-cli board list
```

e usare la porta rilevata.

---

## 19.6 `No serial data received`

Cause comuni:

- board non in bootloader;
- porta sbagliata;
- cavo senza dati;
- porta USB instabile;
- processo che occupa la seriale.

Ripetere la procedura BOOT/RESET e controllare nuovamente la porta.

---

## 19.7 Errore relativo alla USB nativa

Se la compilazione segnala che SwitchNet richiede USB nativa, controllare di usare:

```text
esp32:esp32:esp32s3
```

e non una board ESP32 classica.

---

## 19.8 Errore relativo a USB-OTG / TinyUSB

Se la build segnala che è necessaria la modalità USB-OTG/TinyUSB:

```bash
arduino-cli board details --fqbn esp32:esp32:esp32s3
```

Selezionare il valore corrispondente a:

```text
USB-OTG (TinyUSB)
```

e inserirlo nell'FQBN:

```text
esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>
```

---

## 19.9 Firmware troppo grande

Se compare:

```text
Sketch too big
```

controllare:

```bash
arduino-cli core list
```

Verificare che il core utilizzato sia quello previsto dalla build.

Verificare inoltre che:

```text
partitions.csv
```

sia presente nella root del repository.

Compilare la directory completa:

```bash
arduino-cli compile ... .
```

e non una copia isolata di `SwitchNet.ino`.

---

## 19.10 Board si disconnette dopo il flash

Con firmware che usa la USB nativa in modalità device è possibile che il comportamento USB cambi dopo il boot.

Provare:

1. scollegare la board;
2. entrare in BOOT manualmente;
3. ricollegare;
4. controllare `arduino-cli board list`;
5. eseguire un nuovo flash.

---

## 19.11 La board non viene riconosciuta come controller dalla Switch

Controllare:

- USB Mode compilata come USB-OTG/TinyUSB;
- uso della porta USB effettivamente collegata alla USB nativa del SoC;
- cavo dati;
- impostazione "Comunicazione via cavo del Pro Controller" attiva;
- client SwitchNet in esecuzione;
- connettività di rete PC -> ESP32;
- firmware correttamente avviato;
- eventuali errori nel monitor seriale.

---

# 20. Cancellare completamente la flash

Questa operazione non è normalmente necessaria, ma può essere utile se:

- la board proviene da un altro progetto;
- sono presenti configurazioni NVS incompatibili;
- la partition table è stata modificata più volte;
- il firmware presenta comportamenti inspiegabili.

Installare `esptool`.

### Windows

```powershell
python -m pip install esptool
```

Poi:

```powershell
python -m esptool --chip esp32s3 --port COM5 erase-flash
```

### Linux

```bash
python3 -m pip install esptool
```

Poi:

```bash
python3 -m esptool --chip esp32s3 --port /dev/ttyACM0 erase-flash
```

Dopo l'erase rifare un normale upload completo:

```bash
arduino-cli upload ...
```

> [!WARNING]
> `erase-flash` cancella firmware, partizioni e configurazioni salvate.

---

# 21. Procedura rapida Windows

Di seguito un riepilogo dei comandi principali.

```powershell
cd $HOME

git clone https://github.com/d0vere/SwitchNet.git
cd SwitchNet

arduino-cli config init

arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json

arduino-cli core update-index

arduino-cli core install esp32:esp32@3.3.11

arduino-cli core list

arduino-cli board list

arduino-cli board details --fqbn esp32:esp32:esp32s3
```

Individuare quindi il valore corrispondente a:

```text
USB Mode -> USB-OTG (TinyUSB)
```

Compilare:

```powershell
arduino-cli compile --fqbn "esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>" .
```

Flash, ad esempio su `COM5`:

```powershell
arduino-cli upload -v -p COM5 --fqbn "esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>" .
```

Monitor seriale:

```powershell
arduino-cli monitor -p COM5 -c baudrate=115200
```

---

# 22. Procedura rapida Linux

```bash
sudo apt update
sudo apt install -y git curl

cd ~

curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh

export PATH="$HOME/bin:$PATH"

arduino-cli version

git clone https://github.com/d0vere/SwitchNet.git
cd SwitchNet

arduino-cli config init

arduino-cli config add board_manager.additional_urls \
https://espressif.github.io/arduino-esp32/package_esp32_index.json

arduino-cli core update-index

arduino-cli core install esp32:esp32@3.3.11

arduino-cli core list

arduino-cli board list

arduino-cli board details --fqbn esp32:esp32:esp32s3
```

Individuare il valore:

```text
USB Mode -> USB-OTG (TinyUSB)
```

Compilare:

```bash
arduino-cli compile \
  --fqbn "esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>" \
  .
```

Flash, ad esempio su `/dev/ttyACM0`:

```bash
arduino-cli upload \
  -v \
  -p /dev/ttyACM0 \
  --fqbn "esp32:esp32:esp32s3:USBMode=<VALORE_USB_OTG>" \
  .
```

Monitor seriale:

```bash
arduino-cli monitor -p /dev/ttyACM0 -c baudrate=115200
```

---

# 23. Checklist finale

Prima di considerare conclusa l'installazione verificare:

- [ ] ESP32-S3 con USB nativa;
- [ ] cavo USB dati;
- [ ] repository SwitchNet clonato interamente;
- [ ] `SwitchNet.ino` presente;
- [ ] `src/` presente;
- [ ] `partitions.csv` presente;
- [ ] Arduino CLI funzionante;
- [ ] indice Espressif configurato;
- [ ] core `esp32:esp32` installato;
- [ ] target `esp32:esp32:esp32s3`;
- [ ] modalità USB impostata su USB-OTG/TinyUSB;
- [ ] build completata senza errori;
- [ ] porta seriale identificata;
- [ ] primo flash effettuato via USB;
- [ ] partition table inclusa nel flash;
- [ ] firmware avviato;
- [ ] rete configurata;
- [ ] client SwitchNet operativo;
- [ ] comunicazione cablata del Pro Controller abilitata sulla Nintendo Switch.

---

# Note sulla board Waveshare ESP32-S3FH4R2

Se si utilizza la board Waveshare basata su **ESP32-S3FH4R2**, i parametri hardware principali sono:

```text
SoC:       ESP32-S3
Flash:     4 MB
PSRAM:     2 MB
Wi-Fi:     2.4 GHz
USB:       supporto nativo ESP32-S3
```

Come target Arduino partire da:

```text
ESP32S3 Dev Module
esp32:esp32:esp32s3
```

La flash deve essere configurata coerentemente con i **4 MB** disponibili.

Non selezionare arbitrariamente 8 MB o 16 MB.

Per SwitchNet il requisito determinante rimane la modalità:

```text
USB-OTG / TinyUSB
```

e l'utilizzo della connessione USB realmente collegata ai segnali USB nativi dell'ESP32-S3.

---

# Aggiornamenti successivi

Dopo un primo flash USB riuscito e dopo che la partition table prevista da SwitchNet è stata installata correttamente, eventuali sistemi di aggiornamento OTA forniti dal progetto possono essere utilizzati secondo la documentazione della versione di SwitchNet in uso.

Prima di aggiornare:

```bash
cd SwitchNet
git pull
```

Controllare sempre se il repository ha modificato:

- versione Arduino-ESP32 raccomandata;
- `partitions.csv`;
- opzioni USB;
- modalità di compilazione;
- procedura OTA.

Se uno di questi elementi cambia, seguire le indicazioni della versione più recente del progetto prima di eseguire il flash.
