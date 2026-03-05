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
        }
        db.users.insert_one(users)
        return jsonify({"result": "success", "msg": "회원가입이 완료되었습니다."})
# =========================================================

# ============================= Dashboard ================================
# 대시보드 Refresh
@app.route('/dashboard', methods=['GET'])
def update_dashboard():
    # 0) 현재 페이지 정보 get
    user_id = my_id()
    page = request.args.get("page", default=1, type=int)
    sort_method = request.args.get("sort", default="default")
    problem_num = request.args.get("problem_num", type=int)

    page_size = 10
    post_filter = {}
    sort_spec = [("_id", -1)]

    # 1) 문제번호 검색 조건 
    if problem_num is not None:
        post_filter["problem_num"] = problem_num

    # 2) 정렬 / 내 글 보기 조건
    if sort_method in ("default", "recent"):
        sort_spec = [("_id", -1)]
    elif sort_method == "wonder":
        sort_spec = [("wonders", -1), ("_id", -1)]
    elif sort_method == "my_post":
        post_filter["author_id"] = user_id  
        sort_spec = [("_id", -1)]
    else:
        sort_method = "default"
        sort_spec = [("_id", -1)]

    # 3) 전체 개수 / 페이지 수
    total_count = db.posts.count_documents(post_filter)
    page_count = max(1, (total_count + page_size - 1) // page_size)

    # 페이지 보정
    if page < 1:
        page = 1
    if page > page_count:
        page = page_count

    skip_range = (page - 1) * page_size

    # 4) 랭킹 Top3 추출
    rankers = list(db.users.find({}).sort('user_likes', -1).limit(3))

    # 5) 게시물 리스트 조회
    posts = list(
        db.posts.find(post_filter)
        .sort(sort_spec)
        .skip(skip_range)
        .limit(page_size)
    )

    for p in posts:
        p["id"] = str(p["_id"])

    # 6) 사용자 정보 (닉네임, 등수)
    user = db.users.find_one({"id": user_id})

    user_rank = None
    if user:
        my_score = user.get("score", 0)
        user_rank = db.users.count_documents({"score": {"$gt": my_score}}) + 1

    # 7) 안 읽은 알림 목록 조회
    notifications = list(db.notifications.find({"receiver_id": user_id, "isRead": 0}).sort("_id", -1))

    return render_template(
        "dashboard.html",
        page=page,
        user=user,
        user_rank=user_rank,
        rankers=rankers,
        posts=posts,
        page_count=page_count,
        notifications=notifications,
        sort=sort_method,        
        problem_num=problem_num
    )
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

    # 4) 사용자 정보 가져오기
    user_id = my_id()

    # 5) 유저 정보 넘기기
    user = db.users.find_one({"id": user_id})

    user_rank = None
    if user:
        my_score = user.get("score", 0)
        user_rank = db.users.count_documents({"score": {"$gt": my_score}}) + 1

    # 6) 알람 목록 조회
    notifications = list(db.notifications.find({"receiver_id": user_id, "isRead": 0}).sort("_id", -1))
    return render_template("post.html", post=post, comments = comments, user_id = user_id, user = user, user_rank = user_rank, notifications = notifications)

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
    if not user_id:
        return redirect(url_for("show_post", post_id=post_id))
    try:
        oid = ObjectId(post_id)
    except:
        abort(400)

    # 게시글 조회 
    post = db.posts.find_one({"_id": oid}, {"author_id": 1, "title": 1})
    if post is None:
        return jsonify({"result": "failure", "msg": "해당 게시글 없음"}), 404

    # 사용자가 해당 게시글에 궁금해를 누른 적 있나 검사
    had_wonder = db.wonders.find_one({"user_id": user_id, "post_id": oid})
    if had_wonder is not None:
        return redirect(url_for("show_post", post_id=post_id))

    # 닉네임 조회 
    user_doc = db.users.find_one({"id": user_id}, {"nickname": 1, "_id": 0})
    nickname = user_doc.get("nickname", "") if user_doc else user_id

    # 궁금해 기록 저장
    try:
        db.wonders.insert_one({"user_id": user_id, "post_id": oid})
    except DuplicateKeyError:
        return redirect(url_for("show_post", post_id=post_id))

    # 게시글 궁금해 수 증가
    db.posts.update_one({"_id": oid}, {"$inc": {"wonders": 1}})

    # 알림 생성
    author_id = post.get("author_id")
    post_title = post.get("title", "알 수 없는 게시글")

    if author_id and author_id != user_id:
        notify_doc = {
            "receiver_id": author_id,
            "sender_id": user_id,          
            "sender_nickname": nickname,    
            "post_id": oid,                
            "post_title": post_title,     
            "type": "wonder",               
            "isRead": 0
        }
        db.notifications.insert_one(notify_doc)

    # 다시 게시글 페이지로 이동 (GET)
    return redirect(url_for("show_post", post_id=post_id))
        
# =============================== Posts ==================================

    
# ============================== Comments ================================
# 댓글 작성
@app.route("/post/<post_id>/comment", methods=["POST"])
def create_comment(post_id):
    try:
        oid = ObjectId(post_id)
    except:
        abort(404)

    description_receive = request.form.get("description_give", "").strip()
    if not description_receive:
        return redirect(url_for("show_post", post_id=post_id))

    user_id = my_id()
    if not user_id:
        return redirect(url_for("show_post", post_id=post_id))

    user_doc = db.users.find_one({"id": user_id}, {"nickname": 1, "_id": 0})
    nickname = user_doc.get("nickname", "") if user_doc else ""

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

    # 알림 생성
    post = db.posts.find_one({"_id": oid}, {"author_id": 1, "title": 1})
    author_id = post.get("author_id") if post else None
    post_title = post.get("title", "알 수 없는 게시글") if post else "알 수 없는 게시글"
    
    if author_id and author_id != user_id:
        notify_doc = {
            "receiver_id": author_id,
            "sender_id": user_id,
            "sender_nickname": nickname,
            "post_id": oid,
            "post_title": post_title,
            "type": "comment",
            "isRead": 0
        }
        db.notifications.insert_one(notify_doc)

    return redirect(url_for("show_post", post_id=post_id))

@app.route("/post/<post_id>/comment/<comment_id>/likes", methods=["POST"])
def likes_comment(post_id, comment_id):
    user_id = my_id()
    if not user_id:
        return redirect(url_for("show_post", post_id=post_id))

    # 1) ID 형식 검사
    try:
        post_oid = ObjectId(post_id)
        comment_oid = ObjectId(comment_id)
    except:
        abort(400)

    # 2) 댓글 존재 확인 + 해당 게시글 소속 댓글인지 확인
    comment = db.comments.find_one({"_id": comment_oid, "post_id": post_oid})
    if comment is None:
        return redirect(url_for("show_post", post_id=post_id))

    # 3) 중복 좋아요 검사 (likes 컬렉션)
    had_like = db.likes.find_one({
        "user_id": user_id,
        "comment_id": comment_oid
    })
    if had_like is not None:
        return redirect(url_for("show_post", post_id=post_id))

    # 4) likes 컬렉션에 좋아요 기록 저장
    try:
        db.likes.insert_one({
            "user_id": user_id,
            "comment_id": comment_oid
        })
    except DuplicateKeyError:
        return redirect(url_for("show_post", post_id=post_id))

    # 5) 댓글 작성자의 받은 좋아요 수 증가
    comment_owner_id = comment.get("user_id")
    if comment_owner_id:
        db.users.update_one(
            {"id": comment_owner_id},
            {"$inc": {"user_likes": 1}}
        )

    # 6) 댓글 좋아요 수 증가
    db.comments.update_one(
        {"_id": comment_oid},
        {"$inc": {"comment_likes": 1}}
    )

    # 7) 알림 생성 (댓글 작성자에게)
    # 자기 댓글에 자기가 누른 경우는 알림 생략
    if comment_owner_id and comment_owner_id != user_id:
        # 닉네임
        sender_doc = db.users.find_one({"id": user_id}, {"nickname": 1, "_id": 0})
        sender_nickname = sender_doc.get("nickname", "") if sender_doc else user_id

        # 게시글 제목
        post_doc = db.posts.find_one({"_id": post_oid}, {"title": 1, "_id": 0})
        post_title = post_doc.get("title", "알 수 없는 게시글") if post_doc else "알 수 없는 게시글"

        notify_doc = {
            "receiver_id": comment_owner_id,    #
            "sender_id": user_id,               
            "sender_nickname": sender_nickname, 
            "post_id": post_oid,               
            "post_title": post_title,        
            "type": "like",
            "isRead": 0
        }
        db.notifications.insert_one(notify_doc)

    return redirect(url_for("show_post", post_id=post_id))

# ============================== Comments ================================

# ============================= notifications ============================
@app.route("/notifications/<notification_id>/go", methods=["POST"])
def go_notification_page(notification_id):
    user_id = my_id()
    if not user_id:
        return redirect(url_for("update_dashboard"))

    try:
        oid = ObjectId(notification_id)
    except:
        abort(400)

    notify = db.notifications.find_one({"_id": oid, "receiver_id": user_id})
    if not notify:
        return redirect(url_for("update_dashboard"))

    post_id = str(notify.get("post_id"))

    db.notifications.delete_one({"_id": oid, "receiver_id": user_id})
    return redirect(url_for("show_post", post_id=post_id))

if __name__ == "__main__":
	    app.run("0.0.0.0", port=5000, debug=True)