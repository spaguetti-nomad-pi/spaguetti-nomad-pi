# First boot: Raspberry Pi 5 (NVMe)

Guía para pasar de una SD con Raspberry Pi OS Desktop a un sistema **Lite** instalado en el NVMe, y conectarse por SSH.

> **Cuidado:** los comandos de formateo y flasheo borran **todo** el disco destino. Confirmá el dispositivo con `lsblk` antes de continuar.

---

## 1. Actualizar el sistema de la SD

Con la Pi arrancada desde la SD (OS Desktop):

```bash
sudo apt update && sudo apt full-upgrade -y
```

Si hay paquetes a medio configurar:

```bash
sudo dpkg --configure -a
```

---

## 2. Instalar Raspberry Pi Imager

Si no está instalado:

```bash
sudo apt install rpi-imager -y
```

---

## 3. Descargar Raspberry Pi OS Lite (64-bit)

1. Abrí [https://downloads.raspberrypi.com/raspios_lite_arm64/images/](https://downloads.raspberrypi.com/raspios_lite_arm64/images/).
2. Entrá a la carpeta más reciente.
3. Descargá el archivo `*-arm64-lite.img.xz`.

Ejemplo de nombre:

```text
2025-12-04-raspios-bookworm-arm64-lite.img.xz
```

---

## 4. Identificar el disco NVMe

```bash
lsblk
```

Anotá el dispositivo correcto (por ejemplo `/dev/nvme0n1`). **No** uses la SD (`mmcblk0`).

---

## 5. Formatear el NVMe

Borra firmas de sistemas de archivos y la tabla de particiones:

```bash
sudo wipefs -a /dev/nvme0n1
sudo sgdisk --zap-all /dev/nvme0n1
```

Reemplazá `/dev/nvme0n1` si tu disco es otro.

---

## 6. Flashear la imagen Lite

```bash
sudo rpi-imager --cli 2025-12-04-raspios-bookworm-arm64-lite.img.xz /dev/nvme0n1
```

Sustituí el nombre del `.img.xz` y el dispositivo por los tuyos.

---

## 7. Priorizar el arranque desde NVMe

### Opción A — raspi-config

```bash
sudo raspi-config
```

**Advanced Options → Boot Order → NVMe/USB Boot**

### Opción B — EEPROM a mano

```bash
sudo rpi-eeprom-config --edit
```

Dejá (o agregá) esta línea:

```text
BOOT_ORDER=0xf416
```

---

## 8. Reiniciar sin la SD

```bash
sudo reboot
```

Cuando arranque de nuevo, **sacá la tarjeta SD**. La Pi debería iniciar desde el NVMe.

---

## 9. Conectarte por SSH

Desde otra máquina en la misma red:

```bash
ssh tu_usuario@tu_hostname.local
```

Si no resolvés el hostname, buscá la IP:

```bash
nmap -sn 192.168.1.0/24
```

Ajustá el rango (`192.168.1.0/24`) a tu red. Después:

```bash
ssh tu_usuario@192.168.x.x
```
