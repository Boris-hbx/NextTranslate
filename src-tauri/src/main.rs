//! NextTranslate 桌面应用入口
//!
//! 基于 Tauri 2.0 构建的文档翻译应用

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{Manager, WindowEvent};
use log::{info, error};

mod flask;
mod commands;

use flask::get_flask_manager;
use commands::*;

fn main() {
    // 初始化日志
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info"))
        .init();

    info!("Starting NextTranslate...");

    // 构建 Tauri 应用
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            info!("Setting up application...");

            // 启动 Flask 后端
            let flask_manager = get_flask_manager();

            if let Err(e) = flask_manager.start() {
                error!("Failed to start Flask: {}", e);
                // 不要直接退出，让用户看到错误
            }

            // 异步等待 Flask 就绪后显示窗口
            let main_window = app.get_webview_window("main").unwrap();
            let window_clone = main_window.clone();

            tauri::async_runtime::spawn(async move {
                let flask_manager = get_flask_manager();

                // 等待 Flask 就绪
                match flask_manager.wait_ready(15).await {
                    Ok(_) => {
                        info!("Flask is ready, showing window");
                        // 恢复窗口状态
                        if let Some(state) = load_window_state() {
                            let _ = window_clone.set_size(tauri::Size::Physical(
                                tauri::PhysicalSize::new(state.width, state.height)
                            ));
                            let _ = window_clone.set_position(tauri::Position::Physical(
                                tauri::PhysicalPosition::new(state.x, state.y)
                            ));
                            if state.maximized {
                                let _ = window_clone.maximize();
                            }
                        }
                        let _ = window_clone.show();
                        let _ = window_clone.set_focus();
                    }
                    Err(e) => {
                        error!("Flask failed to start: {}", e);
                        // 仍然显示窗口，让用户看到错误
                        let _ = window_clone.show();
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_app_info,
            check_flask_status,
            restart_flask,
            open_data_dir,
            get_data_dir,
            save_window_state,
            load_window_state,
        ])
        .on_window_event(|window, event| {
            match event {
                WindowEvent::CloseRequested { .. } => {
                    info!("Window close requested");

                    // 保存窗口状态
                    if let Ok(size) = window.outer_size() {
                        if let Ok(position) = window.outer_position() {
                            let maximized = window.is_maximized().unwrap_or(false);
                            let state = WindowState {
                                width: size.width,
                                height: size.height,
                                x: position.x,
                                y: position.y,
                                maximized,
                            };
                            let _ = save_window_state(state);
                        }
                    }

                    // 停止 Flask
                    info!("Stopping Flask backend...");
                    let flask_manager = get_flask_manager();
                    flask_manager.stop();

                    // 允许关闭
                    // api.prevent_close(); // 如果要阻止关闭，取消此注释
                }
                WindowEvent::Destroyed => {
                    info!("Window destroyed");
                }
                _ => {}
            }
        })
        .run(tauri::generate_context!())
        .expect("Error while running NextTranslate");
}
