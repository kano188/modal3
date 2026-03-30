import modal
import time
import sys

APP_NAME = "ai-inferbox"
WORKSPACE_DIR = "/workspace"

app = modal.App.lookup(APP_NAME, create_if_missing=True)

image = (
    modal.Image.debian_slim()
    .apt_install("curl")
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir(".", remote_path=WORKSPACE_DIR)
)

def cleanup_old_sandboxes():
    """關鍵：先終止這個 App 下所有舊的 Sandbox"""
    print("🧹 Cleaning up old sandboxes...")
    try:
        # Modal SDK 支持按 app_id 列出所有 Sandboxes
        sandboxes = list(modal.Sandbox.list(app_id=app.app_id))
        
        if not sandboxes:
            print("✅ No existing sandboxes found.")
            return

        print(f"Found {len(sandboxes)} sandbox(es) to terminate...")
        
        terminated_count = 0
        for sb in sandboxes:
            try:
                print(f"  Terminating sandbox: {sb.object_id}")
                sb.terminate(wait=False)   # 不等待，快速發送終止指令
                terminated_count += 1
                time.sleep(0.3)            # 避免 API rate limit
            except Exception as e:
                print(f"    Warning: Failed to terminate {sb.object_id}: {e}")
        
        print(f"✅ Successfully terminated {terminated_count} old sandbox(s).")
        
        # 給一點時間讓 Modal 處理終止
        if terminated_count > 0:
            time.sleep(2)
            
    except Exception as e:
        print(f"⚠️ Cleanup encountered an error (possibly first run): {e}")
        # 不讓清理失敗影響新部署

def run_in_sandbox():
    cleanup_old_sandboxes()

    print("🧪 Creating new sandbox...")
    
    sandbox = modal.Sandbox.create(
        app=app,
        image=image,
        timeout=86400,                    # 24小時
        region="ap-northeast-3",
        # idle_timeout=1800,              # 可選：1小時無活動自動停止
    )

    print(f"🚀 New sandbox created → {sandbox.object_id}")

    # 在 sandbox 內後台運行你的主程式
    print("🚀 Starting app.py in background...")
    exec_process = sandbox.exec(
        "sh", "-c",
        f"cd {WORKSPACE_DIR} && nohup python3 app.py > app.log 2>&1 & echo $! > pid.txt"
    )

    # 等待命令發送完成
    exec_process.wait()

    # 讓 GitHub Actions 可以立即結束，不阻塞
    sandbox.detach()

    print("✅ Deployment completed: New sandbox is running, old ones stopped.")
    print(f"📊 Sandbox ID: {sandbox.object_id}")
    print(f"📋 Dashboard: https://modal.com/apps")

if __name__ == "__main__":
    if "--sandbox" in sys.argv:
        run_in_sandbox()
    else:
        print("ℹ️ Please run with --sandbox flag")
