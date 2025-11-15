# Visual Query Builder using React Flow

## Contents


- [Project Setup Guide](#Project-Setup-Guide)
    - [1. Install Python](#1-install-python)
    - [2. Install Visual Studio Code](#2-install-visual-studio-code)
    - [3. Install Docker Desktop](#3-install-docker-desktop)
    - [4. Install Node.js](#4-install-nodejs)
    - [5. Set PowerShell Execution Policy](#5-set-powershell-execution-policy)
    - [6. Set Up and Run the Project](#6-set-up-and-run-the-project)
    - [7. Download and Install Ollama](#7-download-and-install-ollama)
    - [8. Install Python Dependencies](#8-install-python-dependencies)
    - [9. Insert and Run the Generated Pipeline](#9-insert-and-run-the-generated-pipeline)
    - [10. Run the Full Pipeline](#10-run-the-full-pipeline)
    - [11. Finishing things up](#11-finishing-things-up)
- [Archive](#archive)

 # Project Setup Guide
Follow these step-by-step instructions to get your visual query pipelines running.  This Guide is Primarily for Windows
**No prior experience required!**

---

## 1. Install Python

- **Get the newest stable version** (no pre-release).  
  Current recommended: **3.13.5**
### Windows
- [Download Python here](https://www.python.org/downloads/)
- Run the installer:
  - **Check:** “Use admin privileges when installing py.exe”
  - **Check:** “Add python.exe to PATH”
  - Click **Install Now**
- When the installation completes, close the installer.
### macOS

Download the macOS installer for Python 3.13.5.
- [Download Python here](https://www.python.org/downloads/)

- Open the downloaded .pkg and follow the on‑screen instructions.

---

## 2. Install Visual Studio Code
### Windows
- [Download VS Code](https://code.visualstudio.com/download)
- Run the installer:
  - **Check all available boxes**
  - Complete the installation
### macOS
- [Download VS Code](https://code.visualstudio.com/download)
- Open the .dmg and drag Visual Studio Code.app into Applications.




---

## 3. Install Docker Desktop
### Windows
- [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Install Docker (this may take a while)
- **After installation, restart your computer**
- When restarted, Docker should open automatically
  - You can skip creating a Docker account
- If prompted, a terminal will open to install WSL (Windows Subsystem for Linux)
  - **Press any key** to continue the WSL installation
- After WSL finishes, open Docker again and press **Restart**

### macOS
- [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Open the .dmg, drag Docker into Applications, and launch it.
---

## 4. Install Node.js
### Windows
- [Download Node.js](https://nodejs.org/en/download)
- Click the installer that matches your operating system
- Run the installer and follow the normal installation steps

### macOS
- [Download Node.js](https://nodejs.org/en/download)
- Open the .pkg and follow the prompts.

---

## 5. Set PowerShell Execution Policy
### (Windows only)
> Not required on macOS.

- Press `Win + X`, then press `A` to open PowerShell as Administrator
- If prompted, click **Yes**
- Copy and paste this command into PowerShell, then press Enter:

```
Set-Executionpolicy Remotesigned -Scope CurrentUser 
```

---

## 6: Set Up and Run the Project

This is a JavaScript Application using [ReactFlow](https://reactflow.dev/).
It is built with [Vite.js](https://vite.dev/) bundler.
### Windows & macOS

- Open the project folder in VS Code or your terminal.

To run use:
```
npm install
npm run dev 
 ```

In case you have problems with vite try to run:
```
npm install vite --save dev 
 ```

Project structure:

```
project/
├── src/
│   └── assets/       : static resources, mostly icons
│   └── components/   : React UI components
│   └── helpers/      : main logic and functionality functions

```


---

## 7: Download and Install Ollama
### Windows
- Visit: [https://ollama.com/download](https://ollama.com/download)
- Download and install it for your system.

Note: During the installation, you may see prompts to install additional dependencies (such as Microsoft Visual C++ Redistributable). Simply click Yes or Install and let the process complete. These are normal and required for Ollama to function correctly.

Then:
- Press `Win + X`, then press `A` to open PowerShell as administrator.
- If prompted, click **Yes**.

In PowerShell, run:

```
ollama pull gemma3:4b
```
After the model is downloaded, start the server with:
```
ollama serve
```

### macOS
- Download the macOS .dmg from [https://ollama.com/download](https://ollama.com/download)
- Open and install the app.
- In Terminal, run:
```
ollama pull gemma3:4b
```
After the model is downloaded, start the server with:
```
ollama serve
```

## 8: Install Python Dependencies
With the project open, go to the terminal and run:
### Windows


```
py -m ensurepip --upgrade; python -m pip install opencv-python kafka-python ujson
```
### macOS

```
pip install opencv-python kafka-python ujson
```

## 9: Insert and Run the Generated Pipeline
### Windows
In the downloaded file:  
- Press `Ctrl + A` to **select all code**  
- Press `Ctrl + C` to **copy** the code

Go into the file and insert the code generated from the downloaded file:  
`C:\...\running\Topics\Cars\Queries\Query_License_Plate_Recognition\query_license_plate_recognition_optimised_skipping.py`

Then in the target file:
- Press `Ctrl + A` to **select all existing code**  
- Press `Ctrl + V` to **paste the new code**  
- Save with `Ctrl + S`
### macOS

In the downloaded file:

* Press `Command (⌘) + A` to **select all code**
* Press `Command (⌘) + C` to **copy** the code

Go into the file and insert the code generated from the downloaded file:

`
/Users/.../running/Topics/Cars/Queries/Query_License_Plate_Recognition/query_license_plate_recognition_optimised_skipping.py
`

Then in the target file:

* Press `Command (⌘) + A` to **select all existing code**
* Press `Command (⌘) + V` to **paste the new code**
* Save with `Command (⌘) + S`




---
## 10: Run the Full Pipeline

Before Starting make sure that Docker and Ollama are open and running.
### Windows
In a new terminal, type:

> This must be done before each session on Windows in order to run the Scripts.
```
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass 
```
> Running the Scripts.
```
cd running/scripts; .\run_all_scripts.ps1
```
After you are done, a file should appear in the **Results** folder.


### macOS
In a new terminal, type:
```
cd running/scripts && chmod +x run_all_scripts.sh && ./run_all_scripts.sh

```

## 11: Finishing things up
### Windows & macOS
To finish things up and shut down the containers, open a new terminal and run:

```
cd running/Docker; docker-compose -f env-compose.yml down
```

## Archive

Everytime there are any dependencies changes in package.json run:
```
npm install
```
This runs the application in dev mode:
```
npm run dev 
```

