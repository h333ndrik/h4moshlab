# Use the editor on a phone over Wi-Fi

This is the existing editor and genuine codec engine. The Mac processes the videos;
it must stay awake and running. A public Internet service is a later phase.

## On your Mac

Open Terminal in the downloaded project folder (the one containing `tools`). Run:

```sh
eval "$(/opt/homebrew/bin/brew shellenv)"
python3 tools/server.py --lan --port 8766
```

FFmpeg and FFprobe must be installed (`brew install ffmpeg`). The default command
without `--lan` still accepts only connections from the Mac itself.

Open `http://127.0.0.1:8766` on the Mac. Click **Copy phone link**, send that link
to your own phone, and open it in Safari while connected to the same Wi-Fi.
The complete **Phone link** also appears in Terminal. Do not use `127.0.0.1` on
the phone: that address refers to the phone itself.

Allow incoming Python connections if macOS Firewall asks. If automatic detection
chooses the wrong interface, find your Mac's Wi-Fi IPv4 in System Settings and run:

```sh
python3 tools/server.py --lan --lan-address 192.168.1.20 --port 8766
```

Replace that example IP with your actual private Wi-Fi address. Guest networks,
client isolation and some VPNs can prevent devices from reaching each other.
If the port is occupied, choose a different port or stop your previous server.
Press **Control+C** to stop; pending terminal commands only execute after stopping.

## On the phone

Import videos, browse the timeline by swiping, reorder with arrows, and tap the
connector to change a transition. Assemble preview returns to the complete movie.
Export MP4 prepares the movie; if preparation was needed, tap Export MP4 again
when prompted to save it. Safari may show its Downloads menu or open the video;
use its Share/Save controls as needed.

The Mac and phone share imported files and processing jobs. Clip order/settings
are kept separately in each browser session; this is not live collaboration.
Restarting the server clears temporary media and invalidates the pairing link.

## Access and testing limits

Use only on trusted private Wi-Fi: transport is HTTP, not encrypted HTTPS.
The join link pairs the phone using an HttpOnly, SameSite cookie; keep that link
private. Other devices need the join link to read media or submit processing.
Host/Origin validation remains enabled. Do not port-forward or expose this server
to the Internet. Public hosting needs HTTPS and isolated user workspaces.

Automated checks cover pairing/expired access, origin guards, the existing render
engine and Chromium touch emulation. A physical iPhone/Safari test is still needed;
emulation does not establish device codec or download compatibility.
