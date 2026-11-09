import os
import shutil
import subprocess
import sys
import tempfile

# 倉庫設定
SOURCE_REPO = "https://github.com/cluntop/tvbox.git"
TARGET_REPO = "https://github.com/WaykeYu/gotv.git"

# 需要複製並覆蓋的目錄清單（相對路徑）
FOLDERS_TO_COPY = [
    "lib",
    "jar",
]

def run_cmd(cmd, cwd=None):
    """執行命令並處理例外"""
    print(f"執行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        print(f"錯誤訊息:\n{result.stderr}", file=sys.stderr)
        raise RuntimeError(f"命令執行失敗: {' '.join(cmd)}")
    return result.stdout.strip()

def main():
    # 使用系統臨時目錄操作，結束後自動清理
    with tempfile.TemporaryDirectory() as temp_dir:
        src_dir = os.path.join(temp_dir, "source")
        target_dir = os.path.join(temp_dir, "target")

        print("=== 1. 克隆來源倉庫 ===")
        run_cmd(["git", "clone", "--depth", "1", SOURCE_REPO, src_dir])

        print("\n=== 2. 克隆目標倉庫 ===")
        run_cmd(["git", "clone", "--depth", "1", TARGET_REPO, target_dir])

        print("\n=== 3. 同步並覆蓋資料夾 ===")
        for folder in FOLDERS_TO_COPY:
            src_folder = os.path.join(src_dir, folder)
            target_folder = os.path.join(target_dir, folder)

            if not os.path.exists(src_folder):
                print(f"[警告] 來源目錄不存在: {folder}，略過。")
                continue

            # 如果目標目錄已存在，先刪除以確保完整覆蓋（移除已在來源刪除的舊檔）
            if os.path.exists(target_folder):
                shutil.rmtree(target_folder)

            # 複製整個目錄
            shutil.copytree(src_folder, target_folder)
            print(f"[完成] 已覆蓋目錄: {folder}")

        print("\n=== 4. 提交與推送變更 ===")
        # 檢查是否有檔案變動
        status = run_cmd(["git", "status", "--porcelain"], cwd=target_dir)
        if not status:
            print("目錄內容無變更，無需推送。")
            return

        print("偵測到以下變動:")
        print(status)

        # 加入所有變更
        run_cmd(["git", "add", "."], cwd=target_dir)

        # 提交變更
        commit_msg = "chore: sync lib and jar from cluntop/tvbox"
        run_cmd(["git", "commit", "-m", commit_msg], cwd=target_dir)

        # 推送到目標倉庫 main 分支
        print("\n正在推送至目標遠端 main 分支...")
        run_cmd(["git", "push", "origin", "main"], cwd=target_dir)

        print("\n=== 全部同步作業已順利完成！ ===")

if __name__ == "__main__":
    main()
