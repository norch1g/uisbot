#!/bin/bash
# ============================================================
# UIS Control Center - Ubuntu Server installer
# Sets up: XFCE desktop + TigerVNC (shared, persistent session)
#          + Python venv + the bot, autostarted in that session.
#
# Run as root (or with sudo):  sudo bash install.sh
# ============================================================
set -e

APP_USER="uisbot"                 # dedicated user that owns the desktop session
APP_DIR="/opt/uisbot"             # where the bot code lives
VNC_DISPLAY="1"                   # :1 -> TCP port 5901
VNC_GEOMETRY="1280x800"
VNC_DEPTH="24"

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root: sudo bash install.sh"
  exit 1
fi

echo "=== 1/7: Installing system packages ==="
apt update
apt install -y \
  tigervnc-standalone-server tigervnc-common \
  xfce4 xfce4-goodies dbus-x11 \
  python3 python3-venv python3-pip python3-tk \
  ufw

echo "=== 2/7: Creating dedicated user '$APP_USER' ==="
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$APP_USER"
  echo "Created user $APP_USER. Set its Linux login password (used to sudo in later if needed):"
  passwd "$APP_USER"
else
  echo "User $APP_USER already exists, skipping creation."
fi

echo "=== 3/7: Deploying bot code to $APP_DIR ==="
mkdir -p "$APP_DIR"
# Copy everything except this installer itself
rsync -a --exclude 'install.sh' --exclude '.git' "$(dirname "$(readlink -f "$0")")/" "$APP_DIR/"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "=== 4/7: Python virtual environment ==="
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "=== 5/7: VNC setup (set a password managers will use to connect) ==="
sudo -u "$APP_USER" mkdir -p "/home/$APP_USER/.vnc"
sudo -u "$APP_USER" vncpasswd "/home/$APP_USER/.vnc/passwd"

cat > "/home/$APP_USER/.vnc/xstartup" << 'XSTARTUP'
#!/bin/bash
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
exec startxfce4
XSTARTUP
chmod +x "/home/$APP_USER/.vnc/xstartup"

# AlwaysShared: multiple managers can view/connect to the SAME live session at once,
# instead of kicking each other out.
cat > "/home/$APP_USER/.vnc/config" << CONFIG
geometry=$VNC_GEOMETRY
depth=$VNC_DEPTH
alwaysshared
CONFIG
chown -R "$APP_USER:$APP_USER" "/home/$APP_USER/.vnc"
chmod 600 "/home/$APP_USER/.vnc/passwd"

echo "=== 6/7: Autostart the bot inside the desktop session ==="
sudo -u "$APP_USER" mkdir -p "/home/$APP_USER/.config/autostart"
cat > "/home/$APP_USER/.config/autostart/uisbot.desktop" << AUTOSTART
[Desktop Entry]
Type=Application
Name=UIS Control Center
Exec=$APP_DIR/venv/bin/python $APP_DIR/bot.py
Path=$APP_DIR
X-GNOME-Autostart-enabled=true
AUTOSTART
chown -R "$APP_USER:$APP_USER" "/home/$APP_USER/.config"

echo "=== 7/7: systemd service for a persistent VNC desktop ==="
cat > /etc/systemd/system/vncserver@.service << SERVICE
[Unit]
Description=TigerVNC persistent desktop session (display :%i)
After=network.target

[Service]
Type=forking
User=$APP_USER
Group=$APP_USER
WorkingDirectory=/home/$APP_USER

# Make sure nothing is left over, then start fresh
ExecStartPre=-/usr/bin/vncserver -kill :%i
ExecStart=/usr/bin/vncserver :%i -geometry $VNC_GEOMETRY -depth $VNC_DEPTH -localhost no
ExecStop=/usr/bin/vncserver -kill :%i

Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable "vncserver@${VNC_DISPLAY}.service"
systemctl restart "vncserver@${VNC_DISPLAY}.service"

echo "=== Firewall ==="
ufw allow 22/tcp    >/dev/null 2>&1 || true   # keep SSH open
ufw allow 590${VNC_DISPLAY}/tcp               # VNC port for display :$VNC_DISPLAY
ufw allow 5000/tcp                            # Flask webhook (UIS -> bot). Restrict this to UIS's IP if possible, see README.
ufw --force enable

echo ""
echo "============================================================"
echo " Done."
echo " VNC address for managers:  <server-ip>:590${VNC_DISPLAY}   (display :${VNC_DISPLAY})"
echo " They'll need a VNC viewer (e.g. TigerVNC Viewer / RealVNC Viewer) and the"
echo " password you just set."
echo " The bot starts automatically with the desktop session and stays running"
echo " even if nobody is connected."
echo " Edit $APP_DIR/settings.ini for the bot token, then restart:"
echo "   sudo systemctl restart vncserver@${VNC_DISPLAY}.service"
echo "============================================================"
