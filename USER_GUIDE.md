# Nuggies Display — User Guide

A Raspberry Pi RGB LED matrix display that cycles through live information: subway departures, stocks, sports scores, weather, and a clock. Controlled entirely from your phone or browser.

---

## First-Time Setup (WiFi)

When the device has no saved WiFi connection, it starts a temporary hotspot so you can configure it.

1. **On your phone or laptop**, open your WiFi settings and connect to:

   | Field | Value |
   |-------|-------|
   | **Network name** | `NuggiesDisplay` |
   | **Password** | `SetUpNuggies` |

2. Once connected, your device may automatically open the setup page. If not, open a browser and go to **`nuggies.local`**.

3. The setup page will show nearby WiFi networks. Select your home network, enter the password, and tap **Connect**.

4. The Pi will reboot automatically. After ~30 seconds, reconnect your phone/laptop to your normal WiFi.

5. The display is now on your network. Access it anytime at **`nuggies.local`** (or `http://nuggies.local:8080`).

---

## Connecting to the Website

Once the Pi is on your WiFi:

- Open a browser on any device on the same network
- Go to: **`nuggies.local`**

The site works on phones, tablets, and desktop browsers.

---

## Display Modes

The display supports five modes, switchable from the **System** page:

| Mode | What it shows |
|------|---------------|
| **Clock** | Current time |
| **MTA** | Next subway departures for your configured NYC station |
| **Sports** | Live / recent scores for MLB, NBA, or NHL |
| **Stocks** | Stock ticker for your configured watchlist |
| **Weather** | Current conditions and forecast |

---

## Switching Modes

### From the website
1. Open the website and go to **System**
2. Under **Switch Mode**, tap the mode you want
3. The display will switch within a few seconds

You can also **Turn Off** the display entirely and **Turn On** again from the same page.

### From the physical buttons

The device has two buttons on the side:

| Action | Result |
|--------|--------|
| Press **Button 1** (left) | Cycle to the previous display mode |
| Press **Button 2** (right) | Cycle to the next display mode |
| Hold **Button 1** for 10 seconds | Restart the Pi |
| Hold **both buttons** for 10 seconds | Factory reset + WiFi wipe (see below) |

> **Note:** The buttons are inactive while the device is in WiFi setup mode (showing the setup screen on the matrix).

---

## Settings

Each mode has its own settings page accessible from the navigation menu:

- **MTA** — Choose your subway station and cycling behavior
- **Stocks** — Set your watchlist and chart intervals
- **Sports** — Pick your league and team
- **Weather** — Set your location
- **Clock** — Set your timezone

---

## Restarting the Pi

If the display freezes or becomes unresponsive:

1. Go to **System** in the website
2. Tap **Restart Pi**
3. Confirm in the dialog
4. The Pi will reboot in ~30 seconds. The display will come back on automatically.

---

## Getting Updates

Software updates are pulled directly from the internet and applied without any manual steps.

1. Go to **System** in the website
2. Under **Pi Actions**, tap **Check for Update**
3. If an update is available, an **Update Available — Install & Reboot** button will appear
4. Tap it and confirm — the Pi will pull the latest code, re-run setup, and reboot (~60 seconds)

---

## Resetting Settings

If you want to wipe your configuration and start fresh:

### Reset Settings only
Goes to **System → Danger Zone → Reset Settings**. Restores all display settings (stocks, weather, clock, MTA) to factory defaults. WiFi stays connected and the display stays on.

### Full Factory Reset (wipes WiFi too)
Goes to **System → Danger Zone → Factory Reset + WiFi Wipe**. This:
- Resets all settings
- Removes all saved WiFi networks
- Reboots the Pi

After the reboot, you'll need to reconnect via the `NuggiesDisplay` hotspot (see [First-Time Setup](#first-time-setup-wifi) above).

---

## Troubleshooting

### Can't reach `nuggies.local`
- Make sure your phone/laptop is on the **same WiFi network** as the Pi
- Try `http://nuggies.local` (with `http://`, not `https://`)
- Some Android devices struggle with `.local` hostnames — try connecting to the Pi's IP address instead (find it in your router's device list)

### Display is blank / frozen
- Go to **System → Turn On** to restart the display process
- If the site is also unreachable, power-cycle the Pi by unplugging and re-plugging it

### Display shows the wrong mode after reboot
- Go to **System** and tap the mode you want — the Pi restores the last active mode on boot

### WiFi setup page didn't appear automatically
- After connecting to `NuggiesDisplay`, open a browser and type `nuggies.local` or `10.42.0.1`
- On iOS, you may need to dismiss any "No Internet" warning and try manually navigating to the address

### Need to move the Pi to a new WiFi network
- Go to **System → Danger Zone → Factory Reset + WiFi Wipe**
- After reboot, connect to `NuggiesDisplay` and follow the [First-Time Setup](#first-time-setup-wifi) steps with your new network credentials
