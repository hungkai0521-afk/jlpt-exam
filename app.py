import os
import json
import re
import time
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from concurrent.futures import ThreadPoolExecutor

print("正在啟動 JLPT 系統 (Fail-Safe Mode)...")

app = Flask(__name__)

# ==========================================
# 您的 API Key
# ==========================================
# 修改後 (請直接替換這段)
import os
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") # 從雲端後台讀取密碼

if not GEMINI_API_KEY:
    raise ValueError("No GEMINI_API_KEY found in environment variables")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# [備援] 如果 AI 完全掛點，回傳這個
BACKUP_DATA = [
    {
        "type": "grammar",
        "script": None,
        "question_text": "【系統】AI 連線逾時，這是本地備援題目。請選 1 繼續。",
        "options": ["繼續", "重試", "等待", "報錯"],
        "correct_index": 0,
        "explanation": "當您看到這題，代表網路連線不穩或 AI 生成太慢，系統自動啟動了備援機制防止卡死。"
    }
]

@app.route('/')
def index():
    return render_template('index.html')

def clean_json_text(text):
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end != -1:
        return text[start : end + 1]
    return text

def generate_worker(params):
    count = params['count']
    level = params['level']
    category = params['category']
    
    # [關鍵修改] 在 Prompt 中強制要求 "explanation" 使用繁體中文
    if category == 'listening':
        prompt = f"""
        Create a JLPT {level} listening set.
        1. Write a SHORT conversation (max 6 lines) using "A:" and "B:".
        2. Create exactly 2 multiple-choice questions based on it.
        3. **IMPORTANT: The "explanation" field MUST be in Traditional Chinese (繁體中文).**
        
        Output JSON Array:
        [
          {{
            "type": "listening",
            "script": "A: ...\\nB: ...", 
            "question_text": "Question?",
            "options": ["A", "B", "C", "D"],
            "correct_index": 0,
            "explanation": "..."
          }}
        ]
        """
    else:
        prompt = f"""
        Generate {count} JLPT {level} {category} multiple-choice questions.
        Output JSON Array only.
        Keys: "type", "script" (null), "question_text", "options", "correct_index", "explanation".
        **IMPORTANT: The "explanation" field MUST be in Traditional Chinese (繁體中文).**
        """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                response_mime_type="application/json"
            )
        )
        cleaned = clean_json_text(response.text)
        return json.loads(cleaned)
    except:
        return []

@app.route('/api/get-questions', methods=['POST'])
def get_questions():
    try:
        data = request.json
        category = data.get('category', 'mock')
        count = data.get('count', 1)
        level = data.get('level', 'N4')

        # 聽力題維持少量 (2題/組)，避免超時
        if category == 'listening':
            final_questions = generate_worker({'count': 2, 'level': level, 'category': category})
        else:
            # 其他題型多執行緒
            with ThreadPoolExecutor(max_workers=2) as executor:
                f1 = executor.submit(generate_worker, {'count': count, 'level': level, 'category': category})
                final_questions = f1.result()

        if not final_questions:
            return jsonify({"status": "success", "data": BACKUP_DATA})

        return jsonify({"status": "success", "data": final_questions})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "success", "data": BACKUP_DATA})

@app.route('/api/analyze-weakness', methods=['POST'])
def analyze_weakness():
    try:
        data = request.json
        mistakes = data.get('mistakes', [])
        
        if not mistakes:
            return jsonify({"status": "success", "analysis": "目前沒有錯題紀錄，表現完美！請繼續保持。"})

        mistake_text = "\n".join([f"- Q: {m['question']} | Correct: {m['correctAnswer']} | User: {m['yourAnswer']}" for m in mistakes[:10]])

        prompt = f"""
        你是日語家教。學生今天做了 JLPT 練習，以下是他的錯題：
        {mistake_text}

        請用繁體中文，針對這些錯誤：
        1. 總結 1 個主要弱點。
        2. 給出 2 個具體的改善建議。
        3. 語氣要簡潔、鼓勵且專業。不要廢話。
        """

        response = model.generate_content(prompt)
        return jsonify({"status": "success", "analysis": response.text})

    except Exception as e:
        print(f"Analysis Error: {e}")
        return jsonify({"status": "error", "analysis": "AI 分析暫時無法使用。"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)