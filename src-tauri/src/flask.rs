//! Flask 后端进程管理模块
//!
//! 负责启动、监控和终止 Flask 后端进程

use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use std::path::PathBuf;
use log::{info, warn};
use sysinfo::{System, Signal};

const FLASK_PORT: u16 = 2008;
const HEALTH_CHECK_URL: &str = "http://localhost:2008/api/health";
const FLASK_EXE_NAME: &str = "flask-backend.exe";

/// Flask 进程管理器
pub struct FlaskManager {
    process: Arc<Mutex<Option<Child>>>,
    exe_path: PathBuf,
}

impl FlaskManager {
    /// 创建新的 Flask 管理器
    pub fn new() -> Self {
        let exe_path = Self::find_flask_exe();
        info!("Flask executable path: {:?}", exe_path);

        Self {
            process: Arc::new(Mutex::new(None)),
            exe_path,
        }
    }

    /// 查找 Flask 可执行文件路径
    fn find_flask_exe() -> PathBuf {
        // 1. 首先检查 resources 目录（打包后）
        if let Ok(exe_dir) = std::env::current_exe() {
            if let Some(parent) = exe_dir.parent() {
                let resource_path = parent.join("resources").join(FLASK_EXE_NAME);
                if resource_path.exists() {
                    return resource_path;
                }

                // Windows 安装目录结构
                let alt_path = parent.join(FLASK_EXE_NAME);
                if alt_path.exists() {
                    return alt_path;
                }
            }
        }

        // 2. 开发模式：检查项目目录
        let dev_paths = [
            "src-tauri/resources/flask-backend.exe",
            "dist/flask-backend.exe",
            "../dist/flask-backend.exe",
        ];

        for path in dev_paths {
            let p = PathBuf::from(path);
            if p.exists() {
                return p;
            }
        }

        // 3. 默认路径
        PathBuf::from("resources/flask-backend.exe")
    }

    /// 清理残留的 Flask 进程
    pub fn cleanup_existing(&self) {
        info!("Cleaning up existing Flask processes...");

        let mut system = System::new_all();
        system.refresh_all();

        for (pid, process) in system.processes() {
            let name = process.name().to_lowercase();
            if name.contains("flask-backend") || name.contains("flask_backend") {
                info!("Killing existing Flask process: PID {}", pid);
                let _ = process.kill_with(Signal::Kill);
            }
        }

        // 等待进程终止
        std::thread::sleep(Duration::from_millis(500));
    }

    /// 检查端口是否被占用
    pub fn is_port_in_use(&self) -> bool {
        use std::net::TcpStream;
        TcpStream::connect(format!("127.0.0.1:{}", FLASK_PORT)).is_ok()
    }

    /// 启动 Flask 进程
    pub fn start(&self) -> Result<(), String> {
        // 先清理残留进程
        self.cleanup_existing();

        // 检查端口
        if self.is_port_in_use() {
            warn!("Port {} is still in use, waiting...", FLASK_PORT);
            std::thread::sleep(Duration::from_secs(1));
            if self.is_port_in_use() {
                return Err(format!("Port {} is already in use", FLASK_PORT));
            }
        }

        // 检查可执行文件
        if !self.exe_path.exists() {
            return Err(format!("Flask executable not found: {:?}", self.exe_path));
        }

        info!("Starting Flask backend: {:?}", self.exe_path);

        // 启动进程
        let child = Command::new(&self.exe_path)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to start Flask: {}", e))?;

        let pid = child.id();
        info!("Flask started with PID: {}", pid);

        // 保存进程句柄
        let mut process = self.process.lock().unwrap();
        *process = Some(child);

        Ok(())
    }

    /// 等待 Flask 就绪
    pub async fn wait_ready(&self, timeout_secs: u64) -> Result<(), String> {
        info!("Waiting for Flask to be ready...");

        let start = std::time::Instant::now();
        let timeout = Duration::from_secs(timeout_secs);

        loop {
            if start.elapsed() > timeout {
                return Err("Flask startup timeout".to_string());
            }

            match self.health_check().await {
                Ok(true) => {
                    info!("Flask is ready!");
                    return Ok(());
                }
                _ => {
                    tokio::time::sleep(Duration::from_millis(200)).await;
                }
            }
        }
    }

    /// 健康检查
    pub async fn health_check(&self) -> Result<bool, String> {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(2))
            .build()
            .map_err(|e| e.to_string())?;

        match client.get(HEALTH_CHECK_URL).send().await {
            Ok(resp) => Ok(resp.status().is_success()),
            Err(_) => Ok(false),
        }
    }

    /// 检查进程是否运行中
    pub fn is_running(&self) -> bool {
        let mut process = self.process.lock().unwrap();
        if let Some(ref mut child) = *process {
            match child.try_wait() {
                Ok(Some(_)) => false,  // 进程已退出
                Ok(None) => true,      // 进程仍在运行
                Err(_) => false,
            }
        } else {
            false
        }
    }

    /// 停止 Flask 进程
    pub fn stop(&self) {
        info!("Stopping Flask backend...");

        // 1. 尝试通过句柄终止
        let mut process = self.process.lock().unwrap();
        if let Some(ref mut child) = *process {
            let pid = child.id();
            info!("Killing Flask process: PID {}", pid);

            // Windows: 终止进程树
            #[cfg(windows)]
            {
                let _ = Command::new("taskkill")
                    .args(["/F", "/T", "/PID", &pid.to_string()])
                    .output();
            }

            // 直接 kill
            let _ = child.kill();
            let _ = child.wait();
        }
        *process = None;

        // 2. 清理任何残留
        self.cleanup_existing();

        info!("Flask backend stopped");
    }
}

impl Drop for FlaskManager {
    fn drop(&mut self) {
        self.stop();
    }
}

/// 全局 Flask 管理器实例
static FLASK_MANAGER: std::sync::OnceLock<FlaskManager> = std::sync::OnceLock::new();

/// 获取全局 Flask 管理器
pub fn get_flask_manager() -> &'static FlaskManager {
    FLASK_MANAGER.get_or_init(FlaskManager::new)
}
