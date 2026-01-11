//! Tauri Commands 模块
//!
//! 提供前端可调用的命令接口

use tauri::command;
use serde::{Deserialize, Serialize};
use crate::flask::get_flask_manager;

/// 应用信息
#[derive(Serialize)]
pub struct AppInfo {
    pub version: String,
    pub name: String,
    pub flask_running: bool,
}

/// 获取应用信息
#[command]
pub fn get_app_info() -> AppInfo {
    let flask_manager = get_flask_manager();

    AppInfo {
        version: env!("CARGO_PKG_VERSION").to_string(),
        name: env!("CARGO_PKG_NAME").to_string(),
        flask_running: flask_manager.is_running(),
    }
}

/// Flask 状态
#[derive(Serialize)]
pub struct FlaskStatus {
    pub running: bool,
    pub healthy: bool,
    pub port: u16,
}

/// 检查 Flask 状态
#[command]
pub async fn check_flask_status() -> FlaskStatus {
    let flask_manager = get_flask_manager();
    let running = flask_manager.is_running();
    let healthy = flask_manager.health_check().await.unwrap_or(false);

    FlaskStatus {
        running,
        healthy,
        port: 2008,
    }
}

/// 重启 Flask 后端
#[command]
pub async fn restart_flask() -> Result<String, String> {
    let flask_manager = get_flask_manager();

    // 停止现有进程
    flask_manager.stop();

    // 等待一下
    tokio::time::sleep(std::time::Duration::from_secs(1)).await;

    // 启动新进程
    flask_manager.start()?;

    // 等待就绪
    flask_manager.wait_ready(10).await?;

    Ok("Flask restarted successfully".to_string())
}

/// 打开数据目录
#[command]
pub fn open_data_dir() -> Result<(), String> {
    let data_dir = get_data_dir();

    #[cfg(windows)]
    {
        std::process::Command::new("explorer")
            .arg(&data_dir)
            .spawn()
            .map_err(|e| e.to_string())?;
    }

    Ok(())
}

/// 获取数据目录路径
#[command]
pub fn get_data_dir() -> String {
    if let Some(local_data) = dirs::data_local_dir() {
        local_data.join("NextTranslate").to_string_lossy().to_string()
    } else {
        "".to_string()
    }
}

/// 窗口状态
#[derive(Serialize, Deserialize)]
pub struct WindowState {
    pub width: u32,
    pub height: u32,
    pub x: i32,
    pub y: i32,
    pub maximized: bool,
}

/// 保存窗口状态
#[command]
pub fn save_window_state(state: WindowState) -> Result<(), String> {
    let data_dir = get_data_dir();
    let state_file = std::path::PathBuf::from(&data_dir).join("window_state.json");

    // 确保目录存在
    if let Some(parent) = state_file.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }

    let json = serde_json::to_string_pretty(&state).map_err(|e| e.to_string())?;
    std::fs::write(&state_file, json).map_err(|e| e.to_string())?;

    Ok(())
}

/// 加载窗口状态
#[command]
pub fn load_window_state() -> Option<WindowState> {
    let data_dir = get_data_dir();
    let state_file = std::path::PathBuf::from(&data_dir).join("window_state.json");

    if state_file.exists() {
        if let Ok(content) = std::fs::read_to_string(&state_file) {
            if let Ok(state) = serde_json::from_str(&content) {
                return Some(state);
            }
        }
    }

    None
}
