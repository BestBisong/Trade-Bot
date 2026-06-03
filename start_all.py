import subprocess
import sys
import os
import time

def main():
    print("=" * 60)
    print("      JARVIS QUANT SYSTEM - ONE-CLICK LAUNCHER")
    print("=" * 60)
    print("[INFO] Starting all services...")

    processes = []
    
    # Path to virtual env python
    if os.name == 'nt':
        python_bin = os.path.join("venv", "Scripts", "python.exe")
    else:
        python_bin = os.path.join("venv", "bin", "python")

    if not os.path.exists(python_bin):
        print(f"[ERROR] Virtual environment python not found at {python_bin}")
        sys.exit(1)

    try:
        # 1. Start FastAPI backend
        print("[INFO] Launching FastAPI Backend on port 8000...")
        backend_proc = subprocess.Popen(
            [python_bin, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000"],
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        processes.append(backend_proc)
        time.sleep(2) # Give it time to start

        # 2. Start Next.js Frontend
        print("[INFO] Launching Next.js Frontend on port 3000...")
        frontend_dir = os.path.abspath("frontend")
        frontend_proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=frontend_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True # Required for running npm on Windows
        )
        processes.append(frontend_proc)
        time.sleep(2)

        # 3. Start Live Trading Bot
        print("[INFO] Launching JARVIS Live Trading Bot (Paper Mode)...")
        # Let the bot output to the terminal directly so the user can watch it trade
        bot_proc = subprocess.Popen(
            [python_bin, "run_bot.py"]
        )
        processes.append(bot_proc)

        print("=" * 60)
        print(" [SUCCESS] All systems running:")
        print("  - Backend API: http://127.0.0.1:8000")
        print("  - Frontend UI: http://localhost:3000")
        print("  - Live Bot: Actively running paper trading scan loop")
        print("=" * 60)
        print(" Press Ctrl+C to stop all services and exit cleanly.")
        print("=" * 60)

        # Keep parent process alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[INFO] Shutdown signal received. Terminating all processes...")
    finally:
        for proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        print("[SUCCESS] All services terminated cleanly.")

if __name__ == "__main__":
    main()
