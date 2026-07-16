# UIS Control Center — Ubuntu Server edition

Changes from the Windows version:
- **Proxy removed.** All Telegram API calls go directly to `api.telegram.org`. Make sure the Ubuntu server itself has unblocked access to Telegram (test with `curl https://api.telegram.org`); if it's blocked at the network/hosting level, that has to be solved at the server/network level, not re-added in code.
- **`os.startfile` (Windows-only) replaced** with a cross-platform opener, so the "Open settings.ini" / "Open subscribers list" buttons work on Linux too.
- The GUI itself (`customtkinter`) is unchanged — same window, same buttons, same logs.

## How managers will access it

Ubuntu servers normally have no screen, so the desktop GUI is shown via a **persistent, shared VNC desktop**:

- One XFCE desktop session runs permanently on the server (started by systemd, survives reboots).
- The bot starts automatically inside that session — it keeps running (webhook + Telegram listener) whether or not anyone is currently connected.
- Any number of managers can connect **at the same time** with a VNC viewer and will all see the *same* live screen (not separate copies) — this matches how they previously RDP'd into the Windows box to check on it.

This is VNC, not RDP — Windows doesn't ship an RDP *server* option that behaves this way, and running one desktop session per RDP login would spawn multiple copies of the bot fighting over the same port. VNC to one shared display avoids that.

Managers will need a VNC viewer app (free): **TigerVNC Viewer** or **RealVNC Viewer** both work fine on Windows/Mac.

## Install

1. Copy this whole folder to the Ubuntu server.
2. Edit `settings.ini` and set your real `tg_token` (a placeholder/old one is currently in there — replace it, and rotate it via @BotFather if it's ever been exposed).
3. Run:
   ```bash
   sudo bash install.sh
   ```
   It will ask you to set a Linux password for the new `uisbot` service account, and a VNC password (this is what managers type in their VNC viewer).
4. Give managers: `<server-ip>:5901` + the VNC password.

## Security notes

- **Plain VNC traffic isn't encrypted.** Fine on a trusted internal LAN or VPN; if managers connect over the open internet, either put the server behind a VPN, or tunnel VNC over SSH (`ssh -L 5901:localhost:5901 user@server`, then point the VNC viewer at `localhost:5901`) rather than opening port 5901 to the world.
- Port `5000` is opened for the UIS webhook (`/uis`). If you know UIS's outgoing IP address, restrict that in the firewall instead of leaving it open to everyone:
  ```bash
  sudo ufw delete allow 5000/tcp
  sudo ufw allow from <UIS_SERVER_IP> to any port 5000 proto tcp
  ```
- The bot token lives in plaintext in `settings.ini` — keep that file's permissions tight (`chmod 600`) and don't commit it to a public repo.

## Day-to-day operations

- Restart everything (desktop + bot): `sudo systemctl restart vncserver@1.service`
- Check status: `sudo systemctl status vncserver@1.service`
- Bot logs (in-app) are also mirrored to `logs/` inside the app folder.
- Config file: `/opt/uisbot/settings.ini`
