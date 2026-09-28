# DAAN545 — Flight Delay Analysis

Group project repo for DAAN545 (Data Mining). Use this as the shared place for code, notebooks, and docs.

**Repo:** https://github.com/mlmirk/DAAN545-flight-delay-analysis

---

## What you need

| Tool | Who needs it | Notes |
|------|----------------|-------|
| [Cursor](https://cursor.com) | Everyone | You already have this (or install it) |
| [Python 3.10+](https://www.python.org/downloads/) | Everyone | Check “Add python.exe to PATH” during install |
| [Git](https://git-scm.com/download/win) | Everyone | Most people do **not** have this yet — install it below |
| [GitHub account](https://github.com/signup) | Everyone | Free account is fine |

---

## 1. Create a GitHub account (if you don’t have one)

1. Go to https://github.com/signup
2. Use your school email if you can
3. Verify your email
4. Tell Michael your **GitHub username** so he can add you to the repo

After you’re invited, open the email (or check https://github.com/notifications) and click **Accept invitation**.

---

## 2. Install Git (Windows)

Git is what lets your computer talk to GitHub. Cursor alone is not enough for sharing code.

### Option A — installer (easiest)

1. Download: https://git-scm.com/download/win
2. Run the installer
3. You can leave all defaults
4. **Important:** when asked about PATH, keep “Git from the command line and also from 3rd-party software”
5. Finish, then **fully quit and reopen Cursor** (so it sees Git)

### Option B — winget (if you like terminals)

```powershell
winget install --id Git.Git -e --source winget
```

Then fully quit and reopen Cursor.

### Check that Git works

In Cursor: **Terminal → New Terminal**, then run:

```powershell
git --version
```

You should see something like `git version 2.x.x`. If not, restart Cursor again, or restart the PC once.

---

## 3. One-time GitHub login from your machine

Still in the Cursor terminal:

```powershell
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

Use the **same email** as your GitHub account if possible.

Then sign in when Git asks (browser login is normal). The first `git clone` or `git push` will prompt you.

> Tip: Prefer **HTTPS** clone URLs (they start with `https://github.com/...`). When Windows asks how to sign in, choose browser / GitHub login.

---

## 4. Get a local copy of this project

### Recommended: Clone in Cursor

1. In Cursor: **File → New Window** (optional but clean)
2. **Command Palette** (`Ctrl+Shift+P`) → type **Git: Clone**
3. Paste:

   `https://github.com/mlmirk/DAAN545-flight-delay-analysis.git`

4. Pick a folder (example: `C:\Users\<you>\Projects`)
5. When asked, **Open** the cloned folder

### Or clone from the terminal

```powershell
cd $env:USERPROFILE\Projects
git clone https://github.com/mlmirk/DAAN545-flight-delay-analysis.git
cd DAAN545-flight-delay-analysis
```

Then in Cursor: **File → Open Folder** → select `DAAN545-flight-delay-analysis`.

---

## 5. Set up Python for this project

In the project folder terminal:

```powershell
python --version
```

If that fails, try `py --version`. If both fail, install Python from https://www.python.org/downloads/ and check **Add to PATH**, then reopen Cursor.

Create a virtual environment (keeps packages local to this project):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks the activate script:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then run `.\.venv\Scripts\Activate.ps1` again.

You should see `(.venv)` at the start of the terminal line when it’s active.

---

## 6. Day-to-day workflow (simple version)

Do this every time you start working:

```powershell
git pull
```

Make your changes in Cursor. Then:

```powershell
git status
git add .
git commit -m "Short description of what you did"
git push
```

### Branches (recommended once more than one person is editing)

```powershell
git pull
git checkout -b yourname/short-topic
# ... edit files ...
git add .
git commit -m "Describe your change"
git push -u origin yourname/short-topic
```

Then on GitHub: open a **Pull Request** into `main` so teammates can review.

### If something looks wrong

- `git status` — shows what changed
- `git pull` — get teammates’ latest work
- Ask in the group chat before force-pushing or deleting branches

---

## Project layout

```text
DAAN545-flight-delay-analysis/
├── README.md              ← you are here (setup + workflow)
├── requirements.txt       ← Python packages
├── .gitignore             ← files Git should not upload
├── notebooks/             ← Jupyter / exploration notebooks
├── src/                   ← shared Python modules / scripts
├── data/
│   ├── raw/               ← original datasets (often not committed)
│   └── processed/         ← cleaned outputs
├── docs/                  ← notes, plans, writeups
└── reports/               ← figures / exported slides
```

Put large data files in `data/raw/` locally. Prefer links or shared drive notes in `docs/` instead of uploading huge CSVs to GitHub.

Data provenance (BTS + OpenFlights airports, cleaning notes): [`docs/data_sources.md`](docs/data_sources.md).

Domain / analysis terms for the writeup: [`docs/glossary.md`](docs/glossary.md).

---

## Quick glossary

| Word | Meaning |
|------|---------|
| **Repository (repo)** | This project folder on GitHub |
| **Clone** | Download a full copy to your computer |
| **Commit** | A saved checkpoint of your changes |
| **Push** | Upload your commits to GitHub |
| **Pull** | Download newest commits from GitHub |
| **Branch** | A separate line of work so you don’t overwrite `main` |
| **Pull Request (PR)** | Ask to merge your branch into `main` |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `git` not recognized | Reinstall Git, then fully restart Cursor |
| Permission denied / can’t see repo | Accept the GitHub invite; confirm you’re logged into the right account |
| `python` not recognized | Reinstall Python with PATH enabled; restart Cursor |
| Activate.ps1 error | Run the `Set-ExecutionPolicy` command in section 5 |
| Merge conflict | Stop and message the group — don’t guess |

---

## Team checklist

- [ ] GitHub account created
- [ ] Invited + invitation accepted
- [ ] Git installed (`git --version` works)
- [ ] Repo cloned and opened in Cursor
- [ ] `.venv` created and `requirements.txt` installed
- [ ] Can `git pull` successfully
