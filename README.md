# DIANA VPN Web Panel

Web tunneling panel modern dengan fitur manajemen akun SSH, VMESS, VLESS, TROJAN, dan SHADOWSOCKS. Panel ini mendukung update otomatis dari repository GitHub.

## Fitur
- **Manajemen User**: Sistem Login dan Register dengan desain Glassmorphism yang mewah.
- **Dashboard Admin**: Monitoring status CPU dan RAM secara real-time.
- **Manajemen Protokol**: Buat dan hapus akun untuk:
  - SSH
  - VMESS (WS/TLS support)
  - VLESS
  - TROJAN
  - SHADOWSOCKS
- **Auto Update**: Fitur update satu klik yang terintegrasi dengan repository `https://github.com/DEDIPREMIUM/ofsweb`.

## Persyaratan Sistem
- VPS dengan OS Ubuntu 20.04+ atau Debian 10+
- Python 3.8+
- Koneksi Internet

## Instalasi

Jalankan perintah berikut di terminal VPS Anda:

```bash
# 1. Clone Repository
git clone https://github.com/DEDIPREMIUM/ofsweb
cd ofsweb

# 2. Berikan Izin Eksekusi pada Setup
chmod +x setup.sh

# 3. Jalankan Instalasi Otomatis
./setup.sh
```

## Menjalankan Aplikasi

Setelah instalasi selesai, jalankan aplikasi dengan perintah:

```bash
python3 app.py
```
Atau jalankan di background:
```bash
nohup python3 app.py > app.log 2>&1 &
```

Akses panel melalui browser di: `http://IP-VPS-ANDA:5000`

## Penggunaan
1. Buka halaman login.
2. Jika belum punya akun, klik "Daftar" (Sign Up) untuk membuat akun admin pertama.
3. Login menggunakan email dan password yang didaftarkan.
4. Di Dashboard, Anda dapat membuat akun VPN dan memantau status server.
5. Untuk memperbarui panel ke versi terbaru, klik menu **Update** di sidebar.

## Struktur Project
- `app.py`: Core backend Flask.
- `models.py`: Definisi database (User, VPNAccount).
- `templates/`: File HTML frontend.
- `setup.sh`: Script instalasi dependensi.

## Catatan
- Pastikan port 5000 (atau port yang Anda konfigurasi) sudah dibuka di firewall VPS Anda.
- Secara default, fitur "Create Account" hanya menyimpan data di database. Untuk integrasi penuh dengan backend VPN (seperti Xray/Sing-box), script backend tambahan perlu diintegrasikan pada `app.py`.

---
© 2024 DEDIPREMIUM
