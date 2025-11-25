# FrootVPN Setup Guide for WSL

This guide walks through setting up FrootVPN with OpenVPN in WSL (Windows Subsystem for Linux).

## Prerequisites

- WSL2 with Debian/Ubuntu
- FrootVPN account credentials
- Sudo access

## Step 1: Install OpenVPN

```bash
# Update package list
sudo apt update

# Install OpenVPN
sudo apt install openvpn -y

# Verify installation
openvpn --version
```

## Step 2: Download FrootVPN Configuration Files

You have two options:

### Option A: Download via WSL (recommended)

```bash
# Create directory for VPN configs
mkdir -p ~/frootvpn
cd ~/frootvpn

# Download FrootVPN config files
# You'll need to get the download link from FrootVPN dashboard
# Typically looks like: https://www.frootvpn.com/api/configs/...
```

### Option B: Download on Windows, copy to WSL

1. Download config files from FrootVPN website on Windows
2. Copy to WSL:
```bash
# From WSL, assuming files are in Windows Downloads:
cp /mnt/c/Users/YOUR_USERNAME/Downloads/frootvpn*.ovpn ~/frootvpn/
```

## Step 3: Create Authentication File

Create a file with your FrootVPN credentials to avoid entering them manually:

```bash
# Create auth file
nano ~/frootvpn/auth.txt
```

Add two lines:
```
your_frootvpn_username
your_frootvpn_password
```

Secure the file:
```bash
chmod 600 ~/frootvpn/auth.txt
```

## Step 4: Test VPN Connection

```bash
# Connect to a server (e.g., US server)
# Replace 'us.ovpn' with your actual config file name
sudo openvpn --config ~/frootvpn/us.ovpn --auth-user-pass ~/frootvpn/auth.txt
```

You should see:
```
Initialization Sequence Completed
```

**Test in another terminal:**
```bash
curl ifconfig.me
```

You should see a different IP address!

Press `Ctrl+C` to disconnect.

## Step 5: Update Project Configuration

Once VPN is working:

1. **Get your baseline IP (VPN OFF):**
```bash
# Make sure VPN is disconnected
curl ifconfig.me
# Example output: 98.123.45.67
```

2. **Update .env file:**
```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/phase1-foundation
nano .env
```

Change:
```
VPN_BASELINE_IP=98.123.45.67  # Your actual non-VPN IP
```

3. **Connect VPN again:**
```bash
sudo openvpn --config ~/frootvpn/us.ovpn --auth-user-pass ~/frootvpn/auth.txt
```

4. **Verify in another terminal:**
```bash
curl ifconfig.me
# Should show VPN IP (different from baseline)
```

## Step 6: Run the Scraper

With VPN connected:

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/phase1-foundation
source venv/bin/activate
export PYTHONPATH=$(pwd)

# Test scraper
PYTHONPATH=$(pwd) venv/bin/python scraper/initial_scrape.py \
  --county wake \
  --start 2024-01-01 \
  --end 2024-01-31 \
  --test \
  --limit 5
```

## Tips

### Run VPN in Background

```bash
# Start VPN in background with logging
sudo openvpn --config ~/frootvpn/us.ovpn \
  --auth-user-pass ~/frootvpn/auth.txt \
  --daemon \
  --log /tmp/openvpn.log

# Check if connected
tail -f /tmp/openvpn.log

# Kill VPN when done
sudo killall openvpn
```

### Quick VPN Commands

```bash
# Connect VPN (foreground)
alias vpn-connect='sudo openvpn --config ~/frootvpn/us.ovpn --auth-user-pass ~/frootvpn/auth.txt'

# Connect VPN (background)
alias vpn-start='sudo openvpn --config ~/frootvpn/us.ovpn --auth-user-pass ~/frootvpn/auth.txt --daemon --log /tmp/openvpn.log'

# Disconnect VPN
alias vpn-stop='sudo killall openvpn'

# Check VPN status
alias vpn-status='curl -s ifconfig.me'
```

Add these to your `~/.bashrc` for convenience.

## Troubleshooting

### "Permission denied" errors
- Make sure to use `sudo` when running OpenVPN
- Check file permissions: `chmod 600 ~/frootvpn/auth.txt`

### VPN connects but internet doesn't work
- WSL2 networking issue
- Try restarting WSL: `wsl --shutdown` (from Windows PowerShell)

### DNS resolution fails
- Add to your .ovpn file:
```
script-security 2
up /etc/openvpn/update-resolv-conf
down /etc/openvpn/update-resolv-conf
```

### Can't download .ovpn files
- Log into FrootVPN dashboard: https://www.frootvpn.com/dashboard
- Go to "Setup" → "OpenVPN"
- Download configuration files for desired servers

## Next Steps

Once VPN is working and scraper can verify it:
1. Run test scrape (5 cases)
2. If successful, increase to 50-100 cases
3. Then run full production scrapes
