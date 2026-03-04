from flask import Flask, render_template, jsonify, request
from pymongo import MongoClient

app = Flask(__name__)

# ================== MongoDB 연결 (환경에 맞게 수정) ============================
client = MongoClient("mongodb://localhost:27017")
db = client["helpjungle"]   # DB 이름
# ================== MongoDB 연결 (환경에 맞게 수정) ============================


# ============================ 최초 화면 렌더링 ============================
@app.route("/auth/login")
def home():
    return render_template("login.html")
# ============================ 최초 화면 렌더링 ============================


# ============================ 회원가입 submit ============================
@app.route("/auth/regist", methods=["POST"])
def auth_regist():
    id_receive = request.form["id_give"]
    pwd_receive = request.form["pwd_give"]
    pwd2_receive = request.form["pwd2_give"]
    nickname_receive = request.form["nickname_receive"]
    
    # 예외 1. 빈값 예외처리 (클라이언트에서 넘어올 때 아무값이 없다면)
    if id_receive == "" or pwd_receive == "" or pwd2_receive == "" or nickname_receive == "":
        return jsonify({"result": "fail", "msg": "모든 값을 입력해주세요."})
    
    # 예외 2. pwd_receive 와 pwd2_receive가 다르다면 비밀번호와 확인비밀번호가 다르므로 예외처리
    elif pwd_receive != pwd2_receive:
        return jsonify({"result": "fail", "msg": "비밀번호를 올바르게 입력했는지 확인해주세요."})

    # 예외 3. id_receive가 기존 DB에 이미 존재한다면 예외처리
    elif id_valid = db.users.find_one({"id" : id_receive}):        
        if id_valid is not None:
        return jsonify({"result": "fail", "msg": "이미 존재하는 아이디입니다."})

    # 예외 4. nickname_receive가 기존 DB에 이미 존재한다면 예외처리
    elif nickname_valid = db.users.find_one({"nickname" : nickname_receive})    
        if nickname_valid is not None:
        return jsonify({"result": "fail", "msg": "이미 존재하는 닉네임입니다."})

    # 위에 2개가 이상이 없다면 mongo db에 사용자 생성
    # 사용자 정보는 DB에 평문저장. 추후 암호화 진행예정
    else:
        users = {
            "id" = id_receive
            "pwd" = pwd_receive
        }
    db.users.insert_one(users)
# ============================ 회원가입 submit ============================


if __name__ == "__main__":
    app.run("0.0.0.0", port=5000, debug=True)