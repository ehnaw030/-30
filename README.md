# 暗雷30（多人在线网页原型）

Python + Flask + Flask-SocketIO。适合先在本机测试，再上传 GitHub 并部署到 Render。

## 本机运行

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

浏览器打开 `http://127.0.0.1:5000`。多人测试时，所有设备需要能访问运行服务器的电脑 IP；部署到 Render 后可通过公开网址加入。

## Render 部署

1. 将整个项目文件夹上传到 GitHub 仓库。
2. 在 Render 选择 New + -> Blueprint，连接该 GitHub 仓库。
3. Render 会读取 `render.yaml` 并安装依赖。
4. 部署完成后打开 Render 提供的网址。

## 当前原型已实现

- 创建房间 / 输入房间号码加入
- 3–6 名玩家限制
- 玩家昵称、积分、位置
- 每位玩家私密暗雷数字
- 两颗骰子与加减运算
- 起点负数重掷一次；仍为负数则扣 5 分并前进 1 格
- 0 点数停留原地
- 触发其他玩家暗雷后的积分转移与暗雷重抽
- 积分归零或为负时淘汰
- 回合实时同步

## 重要：目前仍是测试原型

- 房间资料存在服务器内存中；服务器重启会清空房间。
- 目前尚未实现完整惩罚纸条、幸运免死金牌的取得方式、40 分惩罚流程、最终胜利门槛和下一轮重置流程。
- 暗雷触发后重抽、棋盘循环等规则仍应以设计者提供的完整规则原文为准。
- 当前只适合熟人测试，不应视为经过安全审计的正式服务。
