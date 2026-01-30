# DIANA VPN Web Panel

Web Panel manajemen akun VPN (SSH, Xray VLESS/VMess/Trojan/Shadowsocks) yang ringan dan modern. Dibuat menggunakan Flask (Python) dan Xray-core.

## Fitur Utama

### 1. Manajemen Akun
- **SSH & Xray Support:** Buat dan kelola akun SSH System dan Xray (VLESS, VMess, Trojan, Shadowsocks) dalam satu panel.
- **Pilihan Durasi:** Saat membuat akun, pilih durasi aktif: 3 Hari, 7 Hari, 15 Hari, atau 30 Hari.
- **Expiry Otomatis:** Sistem menghitung tanggal kadaluarsa otomatis.
- **Link Generator:**
  - VLESS/VMess/Trojan: Link TLS (443) dan Non-TLS (80) otomatis digenerate.
  - Tombol **View Link** dan **Copy Link** untuk kemudahan akses.
- **System Users:** Akun SSH dibuat langsung di sistem Linux (useradd) dengan expiry date (chage).
- **Xray Users:** Akun Xray ditambahkan langsung ke konfigurasi JSON Xray dan service direstart otomatis.

### 2. Dashboard Modern
- Tampilan responsif dengan desain Glassmorphism.
- Monitoring status CPU dan RAM server secara real-time.
- Manajemen User (Admin) dengan sistem Approval (Pendaftaran user baru harus disetujui admin).

### 3. Auto-Installer
- Script `setup.sh` otomatis menginstall dan mengkonfigurasi:
  - **Xray-core** (Official Script).
  - **Nginx** sebagai Reverse Proxy (Port 80/443 -> Panel & WebSocket Xray).
  - **Certbot** untuk SSL/HTTPS gratis dari Let's Encrypt.
  - **Python Dependencies** dan **Systemd Service**.

---

## Cara Instalasi

Pastikan Anda menggunakan VPS dengan OS **Ubuntu 20.04+** atau **Debian 10+**. Login sebagai **root**.

1. **Update & Install Git**
   ```bash
   apt-get update && apt-get install git -y
   ```

2. **Clone Repository**
   ```bash
   git clone https://github.com/2026musik-code/ofsweb
   ```

3. **Jalankan Setup**
   ```bash
   cd ofsweb
   chmod +x setup.sh
   ./setup.sh
   ```

4. **Konfigurasi**
   - Script akan meminta **Domain** (pastikan domain sudah diarahkan ke IP VPS).
   - Script akan otomatis menginstall semua dependency dan mengaktifkan SSL.

---

## Cara Penggunaan

1. **Akses Panel**
   Buka browser dan kunjungi: `https://domain-anda.com`

2. **Login Admin Default**
   - **Email:** `admin@diana.com`
   - **Password:** `admin123`
   *(Segera ganti password setelah login!)*

3. **Membuat Akun**
   - Pilih menu protokol di sidebar (misal: VLESS).
   - Masukkan Username.
   - Pilih Durasi (default 30 hari).
   - Klik **Create**.

4. **Update System**
   - Klik menu **Update** di sidebar untuk menarik pembaruan terbaru dari repository GitHub.

---

## Struktur Port (Default)
- **Web Panel:** 5000 (Localhost), diproxy via Nginx (80/443).
- **VLESS WS:** 10001
- **VMess WS:** 10002
- **Trojan WS:** 10003
- **Shadowsocks WS:** 10004
