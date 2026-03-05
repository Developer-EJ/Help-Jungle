from flask import Flask, render_template, jsonify, request, session, redirect, url_for, flash, abort
from pymongo import MongoClient
from bson.objectid import ObjectId
import datetime as dt
from zoneinfo import ZoneInfo
from pymongo.errors import DuplicateKeyError


import jwt
import datetime

app = Flask(__name__)

# jwt 암호키 하드코딩
SECRET_KEY = 'helpjungle_jwt'
app.secret_key = 'helpjungle_jwt'

# 현재 접속된 토큰에서 아이디 찾는 함수
def my_id():
    token_receive = request.cookies.get('mytoken')
    payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
    user_id = payload['id']
    return user_id

# 알림 후 리다이렉션
def alert_redirect(message, url):
    return f'''
        <script>
            alert("{message}");
            window.location.href = "{url}";
        </script>
    '''

# 페이지 랜딩 시 토큰검증 템플릿
# @app.route('/dashboard', methods=['GET'])
# def update_dashboard():
#     token_receive = request.cookies.get('mytoken')
#     try:
#         payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])        
#         return render_template('dashboard.html')
#     except jwt.ExpiredSignatureError:
#         return alert_redirect("로그인 해주세요!", "/")
#     except jwt.exceptions.DecodeError:
#         return alert_redirect("로그인 해주세요!", "/")


# ================== MongoDB 연결 ==================
client = MongoClient("mongodb://localhost:27017")
db = client["helpjungle"]
# ==================================================

# ==================== 최초 화면 렌더링 ====================
@app.route("/")
def home():
    token_receive = request.cookies.get('mytoken')
    
    # 토큰 존재 여부 확인
    if token_receive:        

            # 토큰 복호화 및 유저 정보 조회
            payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])            
            return redirect('/dashboard')
    else:
        # 토큰이 없는 경우
        return render_template("login.html")
# =========================================================

# ========================= 로그인 ========================
@app.route("/auth/login", methods=["POST"])
def auth_login():
    id_receive       = request.form["id_give"]
    pwd_receive      = request.form["pwd_give"]

    # 로그인 정보 받아오기
    result = {
        "id": id_receive,
        "pwd": pwd_receive
    }    
    user = db.users.find_one(result)
    # 로그인 성공 시 JWT 생성
    if user is not None:            
        payload = {
            'id' : id_receive,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=3600)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm = 'HS256')
        return jsonify({"result": "success", "msg": "로그인 성공", "token" : token})
        
    # DB에 로그인 정보 없으면 로그인 실패
    else:
        return jsonify({"result": "fail", "msg": "로그인 실패"})
# =========================================================

# ==================== 회원가입 submit ====================
@app.route("/auth/signUp", methods=["POST"])
def auth_regist():
    id_receive       = request.form["id_give"]
    pwd_receive      = request.form["pwd_give"]
    pwd2_receive     = request.form["pwd2_give"]
    nickname_receive = request.form["nickname_give"]

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
            "nickname": nickname_receive,
            "user_likes": 0,
            "rank": 0,
        }
        db.users.insert_one(users)
        return jsonify({"result": "success", "msg": "회원가입이 완료되었습니다."})
# =========================================================

# ============================= Dashboard ================================
# 대시보드 Refresh
@app.route('/dashboard', methods = ['GET'])
def update_dashboard():
    # 0) 현재 페이지 정보 get
    user_id = my_id()
    page = request.args.get("page", default=1, type=int)
    sort_method = request.args.get("sort", default="default")

    if (sort_method == "my_post"):
        total_count = db.posts.count_documents({"author_id": user_id})
    elif sort_method in ("default", "recent", "wonder"):
        total_count = db.posts.count_documents({})
    page_count = max(1, (total_count + 9) // 10)

    page_size = 10
    skip_range = (page - 1) * page_size
    # 1) 랭킹 Top3 추출
    rankers = list(db.users.find({}).sort('score', -1).limit(3))

    # 2) 게시물 리스트 10개 리스트 업
    post_filter = {}
    sort_spec = [("_id", -1)] 


    if sort_method in ("default", "recent"):
        sort_spec = [("_id", -1)]
    elif sort_method == "wonder":  
        sort_spec = [("wonders", -1), ("_id", -1)]
    elif sort_method == "my_post":
        post_filter = {"author_id": user_id}
        sort_spec = [("_id", -1)]

    posts = list(db.posts.find(post_filter).sort(sort_spec).skip(skip_range).limit(page_size))

    for p in posts:
        p["id"] = str(p["_id"]) 

    # 3) 사용자 정보 (닉네임, 등수)
    user = db.users.find_one({"id": user_id})

    user_rank = None
    if user:
        my_score = user.get("score", 0)  # score 없으면 0 처리
        higher_count = db.users.count_documents({"score": {"$gt": my_score}
        })
        user_rank = higher_count + 1

    # 4) 알람 유무 확인(notifications 컬렉션 열람해서 isRead 컬럼이 1인 데이터 유무 확인)
    has_unread = db.notifications.count_documents({"user_id": user_id, "isRead": 0}) > 0

    return render_template("dashboard.html", page = page, user = user, rankers = rankers, posts = posts, page_count = page_count, has_unread = has_unread)
# ============================= Dashboard ================================

# =============================== Posts ==================================
# 게시물 페이지 출력 
@app.route("/post/<post_id>", methods=["GET"])
def show_post(post_id):
    # 1) ObjectId로 변환
    try:
        oid = ObjectId(post_id)
    except:
        abort(404)

    # 2) 글 조회
    post = db.posts.find_one({"_id": oid})
    if not post:
        abort(404)

    # 3) 댓글 불러오기
    comments = list(db.comments.find({"post_id": oid}))


    return render_template("post.html", post=post, comments = comments)

# 게시물 제작 페이지 출력
@app.route("/post/create", methods=["GET"])
def new_post_page():
    return render_template("createPost.html")

# 게시물 페이지 제작
@app.route("/post/new", methods = ["POST"])
def create_post():
    problem_num_receive = request.form.get("problem_num_give")
    title_receive = request.form.get("title_give")
    content_receive = request.form.get("content_give")

    # 공란 검사
    if not problem_num_receive or not title_receive or not content_receive:
        return jsonify({"result": "fail", "msg": "입력값 공란!"}), 400

    # 형식 검사
    try:
        problem_num_receive = int(problem_num_receive)
    except ValueError:
        return jsonify({"result": "fail", "msg": "형식 오류!"}), 400

    # 게시 시간 및 저자 저장
    user_id = my_id()
    user_doc = db.users.find_one({'id': user_id})
    author_nickname = user_doc.get('nickname') if user_doc else None
    now = dt.datetime.now(ZoneInfo("Asia/Seoul"))
    now_text = f"{now.year}. {now.month}. {now.day}. {now.hour:02d}:{now.minute:02d}"

    doc = {
        "problem_num": problem_num_receive,
        "title": title_receive,
        "content": content_receive,
        "author_id": user_id ,
        "author_nickname": author_nickname,
        "created_at": now_text,
        "wonders": 0,
        "commentCount": 0,
    }
    db.posts.insert_one(doc)
    return jsonify({'result': 'success'}), 201
        
# 게시물 궁금해 버튼
@app.route("/post/<post_id>/wonder", methods=["POST"])
def add_wonder(post_id):
    user_id = my_id()
    try:
        oid = ObjectId(post_id)
    except:
        abort(400)

    post = db.posts.find_one({'_id': oid})
    if post is None:
        return jsonify({'result': 'failure', 'msg': '해당 게시글 없음'}), 404
    
    # 사용자가 해당 게시글에 궁금해를 누른 적 있나 검사
    had_wonder = db.wonders.find_one({'user_id': user_id, 'post_id': oid})
    if had_wonder is not None:
        return jsonify({'result': 'failure', 'msg': '이미 궁금해 눌렀음'}), 409

    try:
        db.wonders.insert_one({"user_id": user_id, "post_id": oid})
    except DuplicateKeyError:
        return jsonify({"result": "failure", "msg": "중복 클릭 감지"}), 409
    
    # 게시글 궁금해 수 증가
    db.posts.update_one({'_id': oid}, {'$inc': {'wonders': 1}})
    updated_post = db.posts.find_one({'_id': oid}, {'wonders': 1})

    return jsonify({
        'result': 'success',
        'wonders': updated_post.get('wonders', 0)
    })

        
# =============================== Posts ==================================

    
# ============================== Comments ================================
# 댓글 작성
@app.route("/post/<post_id>/comment")
def create_comment(post_id):
    try:
        oid = ObjectId(post_id)
    except:
        abort(404)

    description_receive = request.form.get("description_give")

    user_id = my_id()
    nickname = db.users.find_one({"user_id": user_id}, {"nickname": 1, "_id": 0})
    now = dt.datetime.now(ZoneInfo("Asia/Seoul"))
    now_text = f"{now.year}. {now.month}. {now.day}. {now.hour:02d}:{now.minute:02d}"

    doc = {
        "user_id": user_id,
        "nickname": nickname,
        "description": description_receive,
        "created_at": now_text,
        "post_id": oid,
        "comment_likes": 0
    }
    db.comments.insert_one(doc)
    return jsonify({'result': 'success'}), 201

# 댓글 좋아요
@app.route("/post/<post_id>/comment/<comment_id>/likes", methods=["POST"])
def likes_comment(post_id, comment_id):
    user_id = my_id()  # 로그인 아이디 문자열
    if not user_id:
        return jsonify({"result": "failure", "msg": "로그인이 필요합니다."}), 401

    # 1) ID 형식 검사
    try:
        post_oid = ObjectId(post_id)
        comment_oid = ObjectId(comment_id)
    except:
        abort(400)

    # 2) 댓글 존재 확인 + 해당 게시글 소속 댓글인지 확인
    comment = db.comments.find_one({"_id": comment_oid, "post_id": post_oid})
    if comment is None:
        return jsonify({"result": "failure", "msg": "해당 댓글 없음"}), 404

    # 3) 중복 좋아요 검사 (likes 컬렉션)
    had_like = db.likes.find_one({
        "user_id": user_id,
        "comment_id": comment_oid
    })
    if had_like is not None:
        return jsonify({"result": "failure", "msg": "이미 좋아요를 눌렀습니다."}), 409

    # 4) likes 컬렉션에 좋아요 기록 저장 (확실히 눌린 경우)
    db.likes.insert_one({
        "user_id": user_id,
        "comment_id": comment_oid
    })

    # 5) 댓글 주인의 likes 개수 + 1
    comment_owner_id = comment.get("user_id")   # 댓글 작성자 id (문자열)

    if comment_owner_id:
        db.users.update_one(
            {"id": comment_owner_id},           # users 컬렉션의 유저 식별 컬럼
            {"$inc": {"user_likes": 1}}
        )

    # 6) 댓글 좋아요 수 증가
    db.comments.update_one(
        {"_id": comment_oid},
        {"$inc": {"wonders": 1}}
    )

    # 7) 증가된 좋아요 수 반환
    updated_comment = db.comments.find_one({"_id": comment_oid}, {"wonders": 1, "_id": 0})
    wonders = updated_comment.get("wonders", 0) if updated_comment else 0

    return jsonify({
        "result": "success",
        "wonders": wonders
    }), 200

# ============================== Comments ================================

if __name__ == "__main__":
	    app.run("0.0.0.0", port=5000, debug=True)