# Start SmartMove on Windows

## 1. Extract the ZIP

Choose **Extract All**. Open the actual project folder containing:

```text
START_SMARTMOVE.bat
run.py
requirements.txt
smartmove
web
data
```

Do not run from inside the ZIP. You do not need to move files out of their folder. A convenient location is `C:\projets\SmartMove_Enterprise_Platform`.

## 2. Install Python 3.12, 64-bit

Use the official Python installer from python.org and select **Add Python to PATH**. Reopen PowerShell after installation. Verify:

```powershell
py -3.12 --version
```

It should show `Python 3.12.x`. The supplied Windows launcher selects this interpreter explicitly when creating the environment. Another existing Python installation need not be removed.

## 3. Start the application

Double-click **START_SMARTMOVE.bat**. An internet connection is needed on the first setup to install the small pinned web-runtime dependencies. The bundled charts, map and imagery need no external CDN.

The launcher creates an isolated `.venv`, initializes six local demo accounts and starts a local server. It stops if installation fails; it does not silently continue after a failed command.

At first launch, Notepad opens `data\LOCAL_CREDENTIALS.txt`. Find the line beginning **Admin**. Use that email and the password on the same line. There is no common default password.

## 4. Open the dashboard

Enter this address in your browser:

```text
http://localhost:8501
```

After signing in as Admin, select **Executive Overview**. Use a maximized desktop browser for the layout closest to the reference. A responsive mobile layout is also included.

Keep PowerShell open. Closing it or pressing Ctrl+C stops the local server. Double-click the same BAT file to start again; your data persists.

## Copy/paste version

Open PowerShell in the extracted folder. For the example location above:

```powershell
cd C:\projets\SmartMove_Enterprise_Platform
```

Then run each command separately:

```powershell
py -3.12 -m venv .venv
```

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```powershell
.\.venv\Scripts\python.exe -m smartmove.bootstrap
```

```powershell
notepad .\data\LOCAL_CREDENTIALS.txt
```

```powershell
.\.venv\Scripts\python.exe run.py
```

This approach does not activate PowerShell scripts, so it avoids `Activate.ps1` execution-policy issues. Do not use `pip` from an unrelated Python environment. Do not use Streamlit for this project.

## Troubleshooting

| Message / symptom | Action |
|---|---|
| `py` not recognized | Reopen PowerShell after Python installation. Ensure the Python launcher was installed. The BAT launcher can also use a valid `python` command. |
| `requirements.txt` not found | You are in the wrong folder. Run `dir`; enter the folder that contains `run.py` and the requirements file. |
| Old environment uses Python 3.10 | Stop SmartMove. Rename that project's `.venv` to `.venv-old`, then run the launcher with Python 3.12 installed. Do not delete the `data` directory. |
| Port 8501 already in use | Stop the older RetainIQ/CareIQ instance, or launch `python run.py --port 8502` with the project's environment and browse port 8502. |
| Wrong password / lockout | Read the generated credentials carefully. After repeated failed attempts, wait for the 15-minute account lockout. A reset message can be generated from the login form. |
| No credentials file after first launch | Read the terminal error. Bootstrap only writes demo credentials when there are no accounts. It does not reset existing user passwords on every launch. |
| Reset or activation requested | Open the newest matching text file in `data\outbox`, copy its token, and paste it into the account recovery/activation screen. No real email is sent. |
| PyArrow / NumPy DLL error | The main dashboard does not need either library. Use the project's `.venv` and `requirements.txt`, not requirements copied from the older projects. |
| Model refresh fails | Browsing existing model outputs still works. Install `requirements-analytics.txt` before requesting a rebuild; see the server log for the actual failure. |
| Dashboard date is not today | Intentional: this is a synthetic dataset with an as-of date of 2026-08-31. It is not a live operating network. |
| Permission denied on a workspace | Use the appropriate account, or review grants as Admin. Drivers and customers are deliberately restricted on the backend. |

To start through PowerShell using the helper script on port 8502:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1 -Port 8502
```

The process-scoped launch applies only to this invocation. Do not change machine-wide policy or disable your security software.

## Safety and packaging

Use synthetic data only. Do not expose the local app directly to other networks. Never share `LOCAL_CREDENTIALS.txt`, outbox tokens, a used authentication database, or environment secrets. Windows startup scripts were source-reviewed, but this build was tested on Linux rather than Windows.
