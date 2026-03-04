from flask import Flask, render_template, jsonify, request
from pymongo import MongoClient

app = Flask(__name__)

# ================== MongoDB 연결 ==================
client = MongoClient("mongodb://localhost:27017")
db = client["helpjungle"]
# ==================================================

# ==================== 최초 화면 렌더링 ====================
@app.route("/auth/login")
def home():
    return render_template("login.html")
# =========================================================

# ==================== 회원가입 submit ====================
@app.route("/auth/regist", methods=["POST"])
def auth_regist():
    id_receive       = request.form["id_give"]
    pwd_receive      = request.form["pwd_give"]
    pwd2_receive     = request.form["pwd2_give"]
    nickname_receive = request.form["nickname_give"]  # 키 이름 통일 권장

    # 예외 1. 빈값 예외처리
    if id_receive == "" or pwd_receive == "" or pwd2_receive == "" or nickname_receive == "":
        return jsonify({"result": "fail", "msg": "모든 값을 입력해주세요."})

    # 예외 2. 비밀번호 불일치
    elif pwd_receive != pwd2_receive:
        return jsonify({"result": "fail", "msg": "비밀번호를 올바르게 입력했는지 확인해주세요."})

    # 예외 3. 아이디 중복 확인    
    elif db.users.find_one({"id": id_receive}) is not None:
        return jsonify({"result": "fail", "msg": "이미 존재하는 아이디입니다."})

    # 예외 4. 닉네임 중복 확인
    elif db.users.find_one({"nickname": nickname_receive}) is not None:
        return jsonify({"result": "fail", "msg": "이미 존재하는 닉네임입니다."})

    # 모든 예외 통과 시 사용자 생성
    else:
        users = {
            "id": id_receive,
            "pwd": pwd_receive,
            "nickname": nickname_receive
        }
        db.users.insert_one(users)
        return jsonify({"result": "success", "msg": "회원가입이 완료되었습니다."})
# =========================================================

if __name__ == "__main__":
    app.run("0.0.0.0", port=5000, debug=True)