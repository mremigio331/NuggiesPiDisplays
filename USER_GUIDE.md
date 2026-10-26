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

2. Once connected, your device may automatically open the setup page. If not, open a browser and go to **`http://10.42.0.1`** (the setup hotspot's address).

3. The setup page will show nearby WiFi networks. Select your home network, enter the password, and tap **Connect**.

4. The Pi will reboot automatically. After ~30 seconds, reconnect your phone/laptop to your normal WiFi.

5. The display is now on your network. Access it anytime at **`<hostname>.local`** (or `http://<hostname>.local:8080`).

> **What's `<hostname>`?** The device advertises itself on your network as `<hostname>.local`, where
> `<hostname>` is whatever name the SD card image was flashed with — the setup process installs mDNS
> (`avahi-daemon`) but never renames the device. For example, if your hostname is `nuggies`, that's
> `nuggies.local`. If your client (some Android devices) can't resolve `.local` names, use the Pi's
> IP address instead — find it in your router's device list.

---

## Connecting to the Website

Once the Pi is on your WiFi:

- Open a browser on any device on the same network
- Go to: **`<hostname>.local`** (the device's hostname, e.g. `nuggies.local` if the hostname is `nuggies`)

The site works on phones, tablets, and desktop browsers.

---

## Display Modes

The display supports five modes, switchable from the **System** page:

| Mode | What it shows |
|------|---------------|
| **Clock** | Current time |
| **MTA** | Next subway departures for your configured NYC station |
| **Sports** | Live / recent scores for NFL, MLB, NBA, NHL, or soccer |
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
| Hold **both buttons** (see below) | Cycle sport / factory reset, with on-screen feedback |

**Holding both buttons together** does different things depending on how long
you hold, and the display tells you what's happening:

| How long you hold | What happens |
|-------------------|--------------|
| Let go before ~3 seconds | Nothing — treated as an accidental press |
| Let go between ~3 and 10 seconds | **In Sports mode:** switches to the next sport (Favorites → MLB → NBA → WNBA → NFL → NCAAF → NHL → NWSL → Premier League → La Liga → Bundesliga). In other modes, nothing happens. |
| Keep holding past ~5 seconds | The screen shows **"FACTORY RESET — Hold Ns"** counting down |
| Keep holding to 10 seconds | The screen shows **"FACTORY RESET"** and the device performs a full factory reset + WiFi wipe (see below) |

So a quick both-button hold in Sports mode is a handy way to flip between
leagues without opening the website — and if you keep holding, it becomes the
factory reset, with a visible countdown so you can let go in time if you didn't
mean to.

> **Note:** The buttons are inactive while the device is in WiFi setup mode (showing the setup screen on the matrix).

---

## Brightness

You can dim the whole display from **System** on the website. This applies
to every mode (clock, sports, stocks, weather, MTA) at once.

Under **Brightness**, pick one:

| Setting | Brightness |
|---------|-----------|
| **Full** | 100% (default) |
| **Medium** | 60% |
| **Low** | 25% |

The display restarts automatically when you change it, so it may go dark
for a few seconds before coming back at the new brightness.

---

## Schedule

The display can change itself automatically at set times — for example weather
in the morning, sports in the afternoon, and the screen off overnight. Set it up
under **Schedule** on the **System** page.

Times use the **device's own local time** — whatever timezone the Pi is set to.

Each rule is a **time** plus one **action**:

| Action | What it does at that time |
|--------|---------------------------|
| **Mode** | Switches to a display mode (Clock, MTA, Sports, Stocks, Weather). For **Sports**, you also pick the league. |
| **Power** | Turns the display **Off** or **On**. |
| **Brightness** | Sets the brightness (1–100). |

To set it up:

1. Open the website and go to **System → Schedule**.
2. Tap **Edit Times**.
3. Tap **Add Time**, pick a time, choose the action, and fill in its option
   (mode + league, on/off, or a brightness number).
4. Add as many rules as you like, then tap **Save**.
5. Tap **Schedule Off** to turn the schedule **On**.

How it behaves:

- A rule runs **only when its time arrives**. Turning the schedule on does **not**
  move the display right away — it waits for the next rule time.
- If a rule's time has already passed today, it runs at that time **tomorrow**.
- You can still switch modes by hand (website or buttons) any time. A manual
  switch stays until the next rule time comes around; the schedule does not
  fight you and does not turn itself off.
- Turn the whole schedule off with the **Schedule On/Off** button — your rules
  are kept for next time.

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

### Restarting a single service

If you'd rather not reboot the whole Pi, the **System → Restart Services** section
lets you restart one piece at a time:

- **Restart API Service** — the backend that the website and display talk to
  (the website will briefly disconnect while it comes back)
- **Restart Display Service** — just the LED matrix process
- **Restart Website Service** — rebuilds / restarts the web UI

This is quicker than a full reboot when only one part is misbehaving.

---

## Getting Updates

Software updates are pulled directly from the internet and applied without any manual steps.

1. Go to **System** in the website
2. Under **Pi Actions**, tap **Check for Update**
3. If an update is available, an **Update Available — Install & Reboot** button will appear
4. (Optional) Expand **"What's included"** to see the list of changes that will be
   installed before you commit to the update
5. Tap the update button and confirm. A progress window opens and streams what the
   Pi is doing — pulling code, installing dependencies, rebuilding, then rebooting.
   The Pi goes offline for about a minute; the window shows a "reconnecting" message
   while it reboots and clears once the device is back.

> **If the update seems stuck:** the progress window shows the live log. If it
> reports a failure instead of rebooting, note the last few lines — they say which
> step failed.

### Beta updates

Most people should leave this off. Normal updates are the ones that have been
tested and approved for everyone.

If you want new features early — before they're approved for everyone — turn on
**Get beta updates** under **Pi Actions**:

1. Go to **System** in the website
2. Under **Pi Actions**, turn on the **Get beta updates** switch
3. Tap **Check for Update** — your Pi now sees the newest beta build

Beta builds are tested but newer, so a problem can show up there first. Turn the
switch back off at any time to go back to approved-only updates on your next
check.

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

### Can't reach `<hostname>.local`
- Make sure your phone/laptop is on the **same WiFi network** as the Pi
- Try `http://<hostname>.local` (with `http://`, not `https://`), substituting the device's hostname (e.g. `http://nuggies.local` if the hostname is `nuggies`)
- Some Android devices struggle with `.local` hostnames — try connecting to the Pi's IP address instead (find it in your router's device list)

### Display is blank / frozen
- Go to **System → Turn On** to restart the display process
- If the site is also unreachable, power-cycle the Pi by unplugging and re-plugging it

### Display shows the wrong mode after reboot
- Go to **System** and tap the mode you want — the Pi restores the last active mode on boot

### WiFi setup page didn't appear automatically
- After connecting to `NuggiesDisplay`, open a browser and go to `http://10.42.0.1` (the setup hotspot's address)
- On iOS, you may need to dismiss any "No Internet" warning and try manually navigating to the address

### Need to move the Pi to a new WiFi network
- Go to **System → Danger Zone → Factory Reset + WiFi Wipe**
- After reboot, connect to `NuggiesDisplay` and follow the [First-Time Setup](#first-time-setup-wifi) steps with your new network credentials
