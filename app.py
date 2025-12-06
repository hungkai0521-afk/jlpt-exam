import os
from flask import Flask, render_template, request, Response
from functools import wraps
from openai import OpenAI

app = Flask(__name__)

# --- 設定你的 API Key ---
# 這裡會自動讀取 Render 或本機 .env 設定的環境變數 
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# --- 安檢系統 (帳號密碼設定) ---
# 你可以在這裡修改你想用的帳號與密碼
USERNAME = 'BKF1105'
PASSWORD = 'AQL0553'

def check_auth(username, password):
    """檢查帳號密碼是否正確"""
    return username == USERNAME and password == PASSWORD

def authenticate():
    """驗證失敗時傳回 401 回應"""
    return Response(
        '無法驗證您的權限，請登入。\nCould not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    """裝飾器：應用於需要保護的路由"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# --- 主程式路由 ---

@app.route('/', methods=['GET', 'POST'])
@requires_auth  # <--- 這裡掛上了鎖頭，進入首頁前會要求登入
def index():
    result = None
    if request.method == 'POST':
        # 取得使用者在網頁輸入的主題 (如果有)
        user_input = request.form.get('topic')
        
        # 如果沒輸入，預設為 "隨機 N4 文法"
        if not user_input:
            user_input = "隨機出題"

        # --- 這裡設定給 AI 的指令 (Prompt) ---
        system_prompt = "你是一位專業的日文老師，專門教導 JLPT N4 檢定。"
        user_message = (
            f"請根據主題「{user_input}」，出 1 題 JLPT N4 等級的單選題。"
            "格式要求：\n"
            "1. 題目 (含漢字與假名)\n"
            "2. 四個選項\n"
            "3. 正確答案\n"
            "4. 簡短解析 (繁體中文)\n"
            "請直接給出題目內容，不要有多餘的開場白。"
        )

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo", # 或 gpt-4o-mini
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            )
            result = response.choices[0].message.content
        except Exception as e:
            result = f"發生錯誤：{str(e)}"

    return render_template('index.html', result=result)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000)) # Render 預設使用 10000 port
    app.run(host='0.0.0.0', port=port)