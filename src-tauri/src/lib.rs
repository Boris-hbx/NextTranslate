//! NextTranslate Tauri 库
//!
//! 导出所有模块供 main.rs 使用

pub mod flask;
pub mod commands;

pub use flask::FlaskManager;
pub use commands::*;
