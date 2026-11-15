---
title: Catching rogue ScreenConnect: rebuilding a Huntress investigation in my lab
date: 2026-11-13
slug: rogue-screenconnect
summary: I rebuilt the rogue ScreenConnect chain Huntress described, detected every stage, found two cheap bypasses of the obvious rule, and caught it again with built-in Windows logging only.
---

I rebuilt the rogue ScreenConnect chain that Huntress described in September 2026, then tried to detect it and break my own detections. The core chain was caught at every stage, two cheap tweaks got past the obvious rule, and built-in Windows logging alone was enough to catch it without Sysmon or an EDR.

Huntress published [Rogue ScreenConnect Installations Across Unrelated Hosts Suggest Worm-Like Activity](https://www.huntress.com/blog/rogue-screenconnect-installations). ScreenConnect is a legitimate remote-support tool, which is exactly why abuse of it is hard to spot. I wanted to answer three questions:

1. Can I detect each stage of the chain with Wazuh and Sigma?
2. How easily can an attacker sidestep the obvious rule?
3. What can a small organisation see without Sysmon or an EDR?

## The attack chain

According to Huntress, attackers used social engineering to install modified ScreenConnect clients, which then ran a four-stage VBScript chain and spread it to any host that connected to them. In order:

1. **Initial access:** a tech-support scam, a phishing installer or a fake refund form installs a rogue ScreenConnect client.
2. **Script-host spawning:** the client (`ScreenConnect.WindowsClient.exe`) repeatedly starts `wscript.exe` to run `1.vbs` to `4.vbs` from a temp folder.
3. **Staging:** the scripts profile the host, pass a state value through files in `%TEMP%`, and download the next stage.
4. **Execution:** `4.vbs` starts PowerShell on `%TEMP%\runner.ps1`, which decrypts and runs the payload.
5. **Persistence:** a Run key named `WindowsServiceHost` points to a `.vbs` file in the user's AppData.
6. **Spread:** when another host connects to an infected client, it receives and runs the same chain.

I reproduced stages 2, 4 and 5, the parts a defender can see on the endpoint, without any of the payloads.

## The lab and a safe emulation

The test machine was a domain-joined Windows 11 VM running Sysmon and a Wazuh 4.14.9 agent, in a Proxmox home lab with Active Directory and a separate Wazuh manager. I reset it to a clean snapshot after testing.

The emulation reproduces the telemetry, not the malware:

- **No real ScreenConnect.** The "client" is a renamed copy of `powershell.exe` called `ScreenConnect.WindowsClient.exe`, so process names match the real chain.
- **Harmless scripts.** Four VBScripts pass a state value through files in `%TEMP%` like the originals, but contain placeholder text and download nothing.
- **Same execution path.** `4.vbs` starts PowerShell on `runner.ps1`, which only sets the `WindowsServiceHost` Run key to an empty `.vbs` file.
- **Self-cleaning.** The script removes everything it created and refuses to run anywhere but a designated test VM.

One honest limit: the fake client's original file name is PowerShell's, not ScreenConnect's. My rules match on the image name, which is what the real chain shows, but a test with a genuine ScreenConnect client is still to do.

## The detections

| Rule | Level | Catches | Log source |
| --- | --- | --- | --- |
| 100510 | 12 | ScreenConnect client spawns wscript or cscript | Sysmon 1 |
| 100511 | 14 | 100510 three or more times in 2 minutes on one host | Correlation |
| 100512 | 10 | Script host runs a single-digit .vbs from Temp (backstop) | Sysmon 1 |
| 100513 | 10 | Script host starts PowerShell -File on a script in Temp | Sysmon 1 |
| 100514 | 12 | Run key set to launch a .vbs | Sysmon 13 |
| 100515 | 12 | ScreenConnect client spawns mshta, rundll32 or regsvr32 | Sysmon 1 |
| 100516 | 12 | ScreenConnect client starts cmd or PowerShell that launches a script | Sysmon 1 |
| 100517 | 12 | ScreenConnect client spawns a script host, without Sysmon | Security 4688 |
| 100518 | 12 | PowerShell writes a Run key pointing to a .vbs, without Sysmon | PowerShell 4104 |

## Results: three failures, then a pass

The full chain was caught on the fourth run. The first three failed for reasons that had nothing to do with the attack and everything to do with how Wazuh handles Windows events.

| Run | Result | Why |
| --- | --- | --- |
| 4 | Pass: all stages caught | 100510 ×3, 100511, 100513, 100514 |
| 2–3 | Fail: only the wscript stage fired | Wazuh stores Windows paths with doubled backslashes, so my patterns never matched |
| 1 | Fail | Built-in rules claimed the PowerShell and Run-key events first |

Wazuh's built-in rules caught fragments on their own: a PowerShell script running from Temp, and an unusual file in a Run key. None of them tied ScreenConnect to the script host, which is the signal Huntress used.

## Trying to break my own rule

The obvious rule caught four of six realistic tweaks. A `cmd /c` wrapper and `mshta` got past it, and two hardened rules now close both.

| Variant | What the attacker changes | Original rules | After hardening |
| --- | --- | --- | --- |
| V1 | cscript instead of wscript | Caught | Caught |
| V2 | Script renamed update.vbs | Caught | Caught |
| V3 | JScript instead of VBScript | Caught | Caught |
| V4 | cmd /c wscript, breaking the parent link | Backstop only | Caught (100516) |
| V5 | ScreenConnect service as the parent | Caught | Caught |
| V6 | mshta running inline VBScript | Missed | Caught (100515) |
| V7 | PowerShell straight from ScreenConnect | Not detected | Not detected, by design |

V7 is a deliberate gap. A technician running PowerShell through ScreenConnect is everyday activity, so alerting on it would bury analysts in noise.

## No Sysmon, no EDR

Two free Windows settings were enough to catch both the script spawning and the persistence: process-creation auditing with command lines (event 4688) and PowerShell script-block logging (event 4104).

| Stage | With Sysmon | Built-in logging only |
| --- | --- | --- |
| ScreenConnect spawns wscript ×4 | 100510 + 100511 | 100517 ×4 |
| wscript starts PowerShell | 100513 | Visible in the 4104 script block |
| Run key points to a .vbs | 100514 | 100518 |

The 4104 alert for the Run key fired about a second before the Sysmon one, because PowerShell logs a script block before it runs.

## Lessons for Wazuh users

- **Paths are stored with doubled backslashes**, and quotes as `\"`. Write path patterns with `\\+` and don't anchor on quote characters.
- **Built-in rules can claim your events first.** When an event already matches a built-in rule (92029, 92301 and 91816 here), add that rule as an extra parent with `if_sid`.
- **Confirm parent IDs on your own manager.** A wrong parent fails silently.

## Contributions and what's next

- [SigmaHQ pull request #6615](https://github.com/SigmaHQ/sigma/pull/6615): the ScreenConnect and Run-key rules.
- [Atomic Red Team pull request #3495](https://github.com/redcanaryco/atomic-red-team/pull/3495): the emulation as a test anyone can run.

Next: a test with a genuine ScreenConnect trial client, and the same approach applied to Red Canary's ClickFix research.

Rules, scripts and full results: [purpleloop/detections/huntress-rmm-wsh](https://github.com/Mohammedalkahala/purpleloop/tree/main/detections/huntress-rmm-wsh)
