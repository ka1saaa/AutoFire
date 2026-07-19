# AutoFire

AutoFire 是一个面向 Windows 的中文桌面提醒与联系人偏好管理工具。它帮助用户在每天指定时间提醒自己打开抖音网页版，并管理准备互动的联系人和常用笑脸表情预览。

> AutoFire 不保存账号或密码，不绕过登录、验证码或平台限制，也不会在后台自动发送消息。用户须在官方页面自行登录，并在每次互动前自行完成最后的发送操作。

## 功能

- 默认打开 `https://www.douyin.com/`，也可在界面中修改；
- 使用已安装的 Microsoft Edge 打开网页，登录状态由浏览器自行保留；
- 联系人昵称/备注的本地录入、剪贴板导入、截图识别、搜索、排序、勾选、全选与取消全选；
- 已选择联系人与随机常用笑脸的预览；联系人清单首次确认或变更后要求再次确认；
- 创建 Windows 当前用户的每日提醒任务，即使窗口关闭也会在设定时间显示提醒；
- 在 `%LOCALAPPDATA%\\AutoFire\\log\\autofire.log` 记录操作与执行结果；本地数据库也保存在同一目录。

## 运行源码

需要 Python 3.11 或更高版本：

```powershell
python app.py
```

程序使用 Python 标准库运行，不需要安装浏览器驱动或第三方运行依赖。

## 日常操作

1. 点击“保存并用 Edge 打开”，在官方网页自行登录，把鼠标停在右上角“消息”入口并打开消息面板。
2. 抖音消息面板鼠标离开会自动收起，因此联系人选择与最终发送都在官方网页内手动完成；回到 AutoFire 后点击“切到联系人页”。
3. 可点击“从截图识别”选择你自己截取的联系人图片；AutoFire 会优先识别头像与火花样式之间的联系人昵称，并先弹出确认框让你修改后再导入。
4. 勾选联系人并生成表情预览，点击“复制本次清单”后照着清单处理；结束后点击“记录本次已手动处理”，程序会直接写入本地执行记录。

## 生成发布包

安装仅用于打包的依赖后运行脚本：

```powershell
python -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

产物位于 `release\\AutoFire\\`，并会同时生成 `release\\AutoFire-windows-x64.zip`。用户下载压缩包、解压并双击 `AutoFire.exe` 即可运行。

当前仓库的现成 Windows 发布包在 [`downloads/AutoFire-windows-x64.zip`](downloads/AutoFire-windows-x64.zip)。

## 数据与隐私

不要将 `%LOCALAPPDATA%\\AutoFire` 内的数据库或日志上传到 GitHub。仓库的 `.gitignore` 已排除常见本地数据文件，但发布前仍应检查提交内容。
