# 固定本地预览

DayFlow 的前端、FastAPI 后端和本地数据库必须同时运行，仅打开静态页面无法完成登录、计时和数据同步。

## 固定链接

本机预览地址始终为：

```text
http://localhost:5174
```

该地址仅能在运行项目的电脑上访问。电脑关机、Windows 用户未登录或网络服务被系统阻止时，本地链接不可用。

## 设置登录后自动启动

在项目根目录打开 PowerShell，执行：

```powershell
.\scripts\install-preview-autostart.ps1
```

脚本会创建当前 Windows 用户的登录启动任务。用户登录后，服务会在后台启动，自动执行数据库迁移，并持续检查前端、后端与数据库健康状态。服务异常退出时会自动恢复。

安装完成后可访问：

- 网站：`http://localhost:5174`
- 登录页：`http://localhost:5174/login`
- 健康检查：`http://localhost:5174/health`

## 取消自动启动

```powershell
.\scripts\uninstall-preview-autostart.ps1
```

该命令会删除登录启动任务，并停止由项目脚本管理的本地预览进程，不会删除数据库数据。

## 公网访问说明

如果需要在其他电脑、手机或电脑关机时继续访问，必须部署完整的前端、后端和 PostgreSQL，并使用 HTTPS 域名。本地 `localhost` 链接不能替代公网部署。
