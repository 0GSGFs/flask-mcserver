# app.py

import subprocess
import threading
import os
import redis
from flask_session import Session
from authlib.integrations.flask_client import OAuth
from functools import wraps
from datetime import timedelta
from flask import (
    Flask,
    request,
    jsonify,
    send_from_directory,
    url_for,
    session,
    redirect,
    render_template,
)

# 创建Flask应用实例
app = Flask(__name__)
app.secret_key = "<随机字符串>"
app.config["SERVER_NAME"] = "localhost:5000"  # 部署时记得改这里
app.config["SESSION_TYPE"] = "redis"
app.config["SESSION_PERMANENT"] = False  # 会话是否是永久性的
app.config["SESSION_KEY_PREFIX"] = "Session:"
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = False  # 如果使用 HTTPS，设置为 True
app.config["SESSION_COOKIE_NAME"] = "session1"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=1)  # 一小时后删除会话
app.config["SESSION_REDIS"] = redis.from_url("redis://localhost:6379")


# 创建session并绑定到app上同时初始化
Session(app)

# GitHub OAuth
white_list = [
    "0GSGFs",
]  # 白名单
oauth = OAuth(app)
github = OAuth(app).register(
    name="github",
    # 存在环境变量里的github验证令牌
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    access_token_url="https://github.com/login/oauth/access_token",
    access_token_params=None,
    authorize_url="https://github.com/login/oauth/authorize",
    authorize_params=None,
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "user:email"},
)

mc_process = None  # mc的进程
log_data = []  # 日志
log_read_stop_event = threading.Event()  # 突然发现好像也不用停止，算了不管了


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_name" not in session:
            print("Request denied")
            log_data.append("Request denied")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


@app.route("/")
def index():
    user = session.get("user_name")
    if user is None:
        login_url = url_for("login", _external=True)
        return f'<p><a href="{login_url}">Login</p>'
    # return send_from_directory(".", "index.html")
    return render_template(
        "index_template.html",
    )


@app.route("/login")
def login():
    redirect_uri = url_for("callback", _external=True)
    return github.authorize_redirect(redirect_uri)


@app.route("/logout")
def logout():
    session.pop("user_name", None)
    return redirect("/")


@app.route("/callback")
def callback():
    # debug
    print("Session state:", session.get("oauth_state"))
    print("Request state:", session.get("state"))

    token = github.authorize_access_token()
    resp = github.get("user", token=token)  # 取出用户数据
    profile = resp.json()

    # dedug
    print("GitHub profile:", profile)
    print("Session ID:", session.sid)
    print("Session data:", session)

    # 是否在白名单中
    if profile.get("login") not in white_list:
        return f"<h1>Sorry, you are not in the whitelist. User: {session["user_name"]}</h1>"

    session["user_name"] = profile.get("login")

    # 删除同用户之前留下的会话
    # keys = r.keys("Session:*")
    # user_name = str(session["user_name"]).decode("utf-8")
    # for key in keys:
    #     data = r.hgetall(key)
    #     if user_name == data:
    #         r.delete(key)

    # 检测用户名是否存在
    if session["user_name"] is None:
        return "<h1>Error: Could not retrieve user information</h1>"

    return redirect("/")


@app.route("/styles.css", methods=["GET"])
@login_required
def styles():
    return send_from_directory(".", "styles.css")


@app.route("/scripts.js", methods=["GET"])
@login_required
def scripts():
    return send_from_directory(".", "scripts.js")


@app.route("/start", methods=["POST"])  # 路由装饰器，调用 app.route 方法定义路由
@login_required
def start_server():
    def check_java_installed() -> bool:
        try:
            subprocess.run(
                ["java", "-version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd="./mc",
            )
            return True
        except:
            return False

    global mc_process
    if mc_process is None:
        # 先检测环境

        mc_process = subprocess.Popen(  # 启动服务器进程
            ["java", "-jar", "server.jar", "nogui"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            universal_newlines=True,
            cwd="<path to your mc server file>",  # 记得改这里
        )

        # 记录输出的函数
        def read_process_output(process):
            global log_data
            while not log_read_stop_event.is_set():
                output = process.stdout.readline()
                if output == "" and process.poll() is not None:
                    break
                if output:
                    log_data.append(output.strip())
                    if len(log_data) > 50:  # 控制日志长度
                        log_data.pop(0)
                    print(output.strip())

        # 同时启动一个线程记录输出
        log_read_stop_event.clear()
        threading.Thread(target=read_process_output, args=(mc_process,)).start()
        log_data.append("**Start the log stream**")
        return jsonify({"status": "started"})
    else:
        return jsonify({"status": "already running"})


@app.route("/stop", methods=["POST"])
@login_required
def stop_server():
    def wait_for_process_to_end(process):
        global mc_process
        process.wait()
        # mc_process = None

    global mc_process
    if mc_process:
        try:  # 如果服务器上次是非正常关闭先试试能否打开
            mc_process.stdin.write("stop\n")
            mc_process.stdin.flush()
            threading.Thread(target=wait_for_process_to_end, args=(mc_process,)).start()

            # 设置为True, 表示停止这个线程
            log_data.append("**Close the log stream**")
            log_read_stop_event.set()
        except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
            pass
        finally:
            mc_process = None
        return jsonify({"status": "stopped"})
    else:
        return jsonify({"status": "not running"})


@app.route("/logs", methods=["GET"])
@login_required
def get_logs():
    global log_data
    return jsonify(log_data)


@app.route("/command", methods=["POST"])
@login_required
def send_command():
    global mc_process
    command = request.json.get("command")
    if mc_process is not None and command:
        mc_process.stdin.write((command + "\n"))
        mc_process.stdin.flush()
        return jsonify({"status": "command sent"})
    else:
        return jsonify({"status": "server not running or invalid command"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
